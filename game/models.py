from django.conf import settings
from django.db import models


class GameRound(models.Model):
    STATUS_OPEN = "open"
    STATUS_CLOSED = "closed"
    STATUS_FINISHED = "finished"
    STATUS_CHOICES = [(s, s) for s in (STATUS_OPEN, STATUS_CLOSED, STATUS_FINISHED)]

    room = models.ForeignKey("rooms.Room", on_delete=models.CASCADE, related_name="rounds")
    number = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=8, choices=STATUS_CHOICES, default=STATUS_OPEN)
    target = models.DecimalField(max_digits=5, decimal_places=2)
    ends_at = models.DateTimeField()
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["number"]
        constraints = [models.UniqueConstraint(fields=["room", "number"], name="unique_room_round")]


class Submission(models.Model):
    round = models.ForeignKey(GameRound, on_delete=models.CASCADE, related_name="submissions")
    player = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="game_submissions")
    number = models.DecimalField(max_digits=5, decimal_places=2)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["round", "player"], name="unique_round_player_submission")]
