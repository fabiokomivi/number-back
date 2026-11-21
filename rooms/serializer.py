from rest_framework import serializers

from .models import Room


class RoomPlayerSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()


class RoomSerializer(serializers.ModelSerializer):
    owner = RoomPlayerSerializer(read_only=True)
    players = RoomPlayerSerializer(many=True, read_only=True)
    can_start = serializers.SerializerMethodField()
    can_start_reason = serializers.SerializerMethodField()

    class Meta:
        model = Room
        fields = ("id", "code", "name", "status", "max_players", "owner", "players",
                  "can_start", "can_start_reason", "starts_at")
        read_only_fields = ("id", "code", "status", "owner", "players", "starts_at")

    def get_can_start(self, room):
        return room.status == Room.STATUS_WAITING and room.players.count() >= 2

    def get_can_start_reason(self, room):
        if room.status != Room.STATUS_WAITING:
            return "La partie a déjà commencé."
        if room.players.count() < 2:
            return "Il faut au moins 2 joueurs pour démarrer."
        return None

    def validate_max_players(self, value):
        if not 2 <= value <= 20:
            raise serializers.ValidationError("La capacité doit être comprise entre 2 et 20.")
        return value

    def validate_name(self, value):
        if value and len(value) > 40:
            raise serializers.ValidationError("Le nom ne peut pas dépasser 40 caractères.")
        return value
