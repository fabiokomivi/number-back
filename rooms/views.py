import secrets
import string
import math

from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from game.services import game_result, game_state, send_room_event, start_game, submit_number
from .models import Room
from .serializer import RoomSerializer


def room_code():
    alphabet = string.ascii_uppercase + string.digits
    while True:
        value = "".join(secrets.choice(alphabet) for _ in range(6))
        if not Room.objects.filter(code=value).exists():
            return value


class RoomViewSet(viewsets.ModelViewSet):
    serializer_class = RoomSerializer
    permission_classes = [IsAuthenticated]
    queryset = Room.objects.prefetch_related("players").select_related("owner")
    http_method_names = ["get", "post", "head", "options"]

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset().exclude(status=Room.STATUS_FINISHED))
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def perform_create(self, serializer):
        room = serializer.save(owner=self.request.user, code=room_code())
        room.players.add(self.request.user)
        send_room_event(room.pk, "ROOM_UPDATED", {"room": RoomSerializer(room).data})

    def retrieve(self, request, *args, **kwargs):
        room = self.get_object()
        self._require_member(room, request.user)
        return Response(self.get_serializer(room).data)

    @staticmethod
    def _require_member(room, player):
        if not room.players.filter(pk=player.pk).exists():
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Vous ne faites pas partie de cette chambre.")

    def _room_response(self, room):
        room = Room.objects.prefetch_related("players").select_related("owner").get(pk=room.pk)
        return Response(RoomSerializer(room).data)

    @action(detail=False, methods=["post"], url_path="join")
    def join_by_code(self, request):
        code = str(request.data.get("code", "")).strip().upper()
        room = Room.objects.filter(code=code).first()
        if room is None:
            return Response({"detail": "Chambre introuvable."}, status=status.HTTP_404_NOT_FOUND)
        return self._join(room, request.user)

    @action(detail=True, methods=["post"])
    def join(self, request, pk=None):
        return self._join(self.get_object(), request.user)

    def _join(self, room, player):
        with transaction.atomic():
            room = Room.objects.select_for_update().get(pk=room.pk)
            if room.players.filter(pk=player.pk).exists():
                return self._room_response(room)
            if room.status != Room.STATUS_WAITING:
                return Response({"detail": "Cette partie a déjà commencé."}, status=400)
            if room.players.count() >= room.max_players:
                return Response({"detail": "Cette chambre est complète."}, status=400)
            room.players.add(player)
        fresh = Room.objects.prefetch_related("players").select_related("owner").get(pk=room.pk)
        send_room_event(room.pk, "PLAYER_JOINED", {"username": player.username, "player": {"id": player.pk, "username": player.username}})
        send_room_event(room.pk, "ROOM_UPDATED", {"room": RoomSerializer(fresh).data})
        return Response(RoomSerializer(fresh).data)

    @action(detail=True, methods=["post"])
    def leave(self, request, pk=None):
        room = self.get_object()
        if not room.players.filter(pk=request.user.pk).exists():
            return Response({"detail": "Vous ne faites pas partie de cette chambre."}, status=400)
        room.players.remove(request.user)
        send_room_event(room.pk, "PLAYER_LEFT", {"player": {"id": request.user.pk, "username": request.user.username}})
        if room.owner_id == request.user.pk:
            next_owner = room.players.order_by("id").first()
            if next_owner:
                room.owner = next_owner
                room.save(update_fields=["owner"])
            else:
                room.delete()
                return Response({"detail": "Vous avez quitté la chambre."})
        fresh = Room.objects.prefetch_related("players").select_related("owner").get(pk=room.pk)
        send_room_event(room.pk, "ROOM_UPDATED", {"room": RoomSerializer(fresh).data})
        return Response(RoomSerializer(fresh).data)

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        room = self.get_object()
        if room.owner_id != request.user.pk:
            return Response({"detail": "Seul le créateur peut démarrer la partie."}, status=403)
        started, result = start_game(room)
        if not started:
            return Response({"detail": result}, status=400)
        fresh = Room.objects.prefetch_related("players").select_related("owner").get(pk=room.pk)
        send_room_event(room.pk, "ROOM_UPDATED", {"room": RoomSerializer(fresh).data})
        return Response(RoomSerializer(fresh).data)

    @action(detail=True, methods=["get"])
    def game(self, request, pk=None):
        room = self.get_object()
        self._require_member(room, request.user)
        return Response(game_state(room, request.user))

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        room = self.get_object()
        self._require_member(room, request.user)
        value = request.data.get("number")
        try:
            number = float(value)
        except (TypeError, ValueError):
            return Response({"number": ["Saisissez un nombre entre 0 et 100."]}, status=400)
        if not math.isfinite(number) or not 0 <= number <= 100:
            return Response({"number": ["Le nombre doit être compris entre 0 et 100."]}, status=400)
        ok, result = submit_number(room, request.user, number)
        if not ok:
            return Response({"detail": result}, status=400)
        return Response({"detail": "Nombre soumis.", **result})

    @action(detail=True, methods=["get"])
    def result(self, request, pk=None):
        room = self.get_object()
        self._require_member(room, request.user)
        return Response(game_result(room))
