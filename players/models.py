from django.db import models
from django.contrib.auth.models import AbstractUser


class Player(AbstractUser):
    telephone = models.CharField(max_length=8, null=True, blank=True, unique=True)
    