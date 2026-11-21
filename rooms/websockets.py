import json
import math

from channels.generic.websocket import WebsocketConsumer
from asgiref.sync import async_to_sync
from django.utils import timezone

from .models import Room
from game.services import submit_number


class RoomConsumer(WebsocketConsumer):

    # Événements que le client est autorisé à envoyer.
    CLIENT_EVENTS = {"SUBMIT_NUMBER", "PING"}

    def connect(self):

        self.room_id = self.scope["url_route"]["kwargs"]["room_id"]
        self.room_group_name = f"room_{self.room_id}"

        user = self.scope["user"]

        if not user.is_authenticated:
            self.close()
            return
        try:
            room = Room.objects.get(pk=self.room_id)
        except Room.DoesNotExist:
            self.close()
            return
        if not room.players.filter(pk=user.pk).exists():
            self.close()
            return
        self.player_id = str(user.pk)
        async_to_sync(self.channel_layer.group_add)(
            self.room_group_name,
            self.channel_name
        )

        self.accept()


    def disconnect(self, close_code):

        if not hasattr(self, "player_id"):
            return

        async_to_sync(self.channel_layer.group_discard)(
            self.room_group_name,
            self.channel_name
        )

        player = self.scope["user"]
        self.broadcast_event("PLAYER_DISCONNECTED", {
            "player": {"id": player.pk, "username": player.username},
        })

    def receive(self, text_data):

        try:
            payload = json.loads(text_data)
            if not isinstance(payload, dict):
                self.send_event("ERROR", {"detail": "Le message doit être un objet JSON."})
                return
            event_type = payload.get("type")
            data = payload.get("payload", payload.get("data", {}))
            if not isinstance(event_type, str) or event_type not in self.CLIENT_EVENTS or not isinstance(data, dict):
                self.send_event("ERROR", {"detail": "Événement ou payload invalide."})
                return
            if event_type == "PING":
                self.send_event("PONG", {})
                return
            if event_type == "SUBMIT_NUMBER":
                try:
                    number = float(data["number"])
                    if not math.isfinite(number) or not 0 <= number <= 100:
                        raise ValueError
                except (KeyError, TypeError, ValueError):
                    self.send_event("ERROR", {"detail": "Le nombre doit être compris entre 0 et 100."})
                    return
                ok, result = submit_number(Room.objects.get(pk=self.room_id), self.scope["user"], number)
                if not ok:
                    self.send_event("ERROR", {"detail": result})
        except (json.JSONDecodeError, Room.DoesNotExist):
            self.send_event("ERROR", {"detail": "Message invalide."})

    # --------------------------------
    # Gestion des événements
    # --------------------------------

    def broadcast_event(self, event, payload):
        async_to_sync(self.channel_layer.group_send)(
            self.room_group_name,
            {
                "type": "room.event", "event_type": event, "payload": payload,
            },
        )

    def room_event(self, event):
        self.send_event(event["event_type"], event["payload"])

    def send_event(self, event_type, payload):
        self.send(text_data=json.dumps({
            "type": event_type,
            "payload": {"server_time": timezone.now().isoformat(), **payload},
        }))

    
