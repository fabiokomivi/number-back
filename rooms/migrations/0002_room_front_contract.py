import django.db.models.deletion
import django.utils.timezone
import rooms.models
from django.conf import settings
from django.db import migrations, models


def populate_room_codes(apps, schema_editor):
    Room = apps.get_model("rooms", "Room")
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    for room in Room.objects.all().iterator():
        while True:
            code = "".join(__import__("secrets").choice(alphabet) for _ in range(6))
            if not Room.objects.filter(code=code).exclude(pk=room.pk).exists():
                room.code = code
                room.save(update_fields=["code"])
                break


class Migration(migrations.Migration):
    dependencies = [
        ("rooms", "0001_initial"),
        ("players", "0002_alter_player_telephone"),
    ]

    operations = [
        migrations.RenameField(model_name="room", old_name="nom", new_name="name"),
        migrations.AlterField(model_name="room", name="name", field=models.CharField(blank=True, max_length=40, null=True)),
        migrations.AlterField(model_name="room", name="max_players", field=models.PositiveSmallIntegerField(default=8)),
        migrations.AddField(model_name="room", name="code", field=models.CharField(blank=True, default="", max_length=12)),
        migrations.RunPython(populate_room_codes, migrations.RunPython.noop),
        migrations.AlterField(model_name="room", name="code", field=models.CharField(default=rooms.models.generate_room_code, max_length=12, unique=True)),
        migrations.AddField(model_name="room", name="status", field=models.CharField(choices=[("waiting", "waiting"), ("playing", "playing"), ("finished", "finished")], default="waiting", max_length=10)),
        migrations.AddField(model_name="room", name="owner", field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="owned_rooms", to=settings.AUTH_USER_MODEL)),
        migrations.AddField(model_name="room", name="players", field=models.ManyToManyField(blank=True, related_name="rooms", to=settings.AUTH_USER_MODEL)),
        migrations.AddField(model_name="room", name="starts_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="room", name="created_at", field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now), preserve_default=False),
    ]
