import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("rooms", "0002_room_front_contract"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="GameRound",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("number", models.PositiveSmallIntegerField()),
                ("target", models.DecimalField(decimal_places=2, max_digits=5)),
                ("ends_at", models.DateTimeField()),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("room", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="rounds", to="rooms.room")),
            ],
            options={"ordering": ["number"]},
        ),
        migrations.CreateModel(
            name="Submission",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("number", models.DecimalField(decimal_places=2, max_digits=5)),
                ("submitted_at", models.DateTimeField(auto_now_add=True)),
                ("player", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="game_submissions", to=settings.AUTH_USER_MODEL)),
                ("round", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="submissions", to="game.gameround")),
            ],
        ),
        migrations.AddConstraint(model_name="gameround", constraint=models.UniqueConstraint(fields=("room", "number"), name="unique_room_round")),
        migrations.AddConstraint(model_name="submission", constraint=models.UniqueConstraint(fields=("round", "player"), name="unique_round_player_submission")),
    ]
