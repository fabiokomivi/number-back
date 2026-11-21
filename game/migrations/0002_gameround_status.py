from django.db import migrations, models


def mark_finished_rounds(apps, schema_editor):
    GameRound = apps.get_model("game", "GameRound")
    GameRound.objects.filter(finished_at__isnull=False).update(status="finished")


class Migration(migrations.Migration):
    dependencies = [("game", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="gameround",
            name="status",
            field=models.CharField(
                choices=[("open", "open"), ("closed", "closed"), ("finished", "finished")],
                default="open",
                max_length=8,
            ),
        ),
        migrations.RunPython(mark_finished_rounds, migrations.RunPython.noop),
    ]
