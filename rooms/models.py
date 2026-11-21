import secrets
import string

from django.conf import settings
from django.db import models


def generate_room_code():
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(6))


class Room(models.Model):
    STATUS_WAITING = "waiting"
    STATUS_PLAYING = "playing"
    STATUS_FINISHED = "finished"
    STATUS_CHOICES = [(s, s) for s in (STATUS_WAITING, STATUS_PLAYING, STATUS_FINISHED)]

    code = models.CharField(max_length=12, unique=True, default=generate_room_code)
    name = models.CharField(max_length=40, null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_WAITING)
    max_players = models.PositiveSmallIntegerField(default=8)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="owned_rooms")
    players = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="rooms", blank=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.code
