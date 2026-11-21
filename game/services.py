import random
import threading
from datetime import timedelta
from decimal import Decimal

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.db import close_old_connections, transaction
from django.utils import timezone

from .models import GameRound, Submission
from rooms.models import Room

TOTAL_ROUNDS = 5


def player_data(player):
    return {"id": player.pk, "username": player.username}


def send_room_event(room_id, event_type, payload=None):
    layer = get_channel_layer()
    if layer:
        async_to_sync(layer.group_send)(f"room_{room_id}", {
            "type": "room.event", "event_type": event_type, "payload": payload or {},
        })


def schedule_round_expiry(round_id, ends_at):
    delay = max(0, (ends_at - timezone.now()).total_seconds())
    timer = threading.Timer(delay, expire_round, args=(round_id,))
    timer.daemon = True
    timer.start()


def expire_round(round_id):
    close_old_connections()
    try:
        room_id = GameRound.objects.values_list("room_id", flat=True).get(pk=round_id)
        with transaction.atomic():
            Room.objects.select_for_update().get(pk=room_id)
            game_round = GameRound.objects.select_for_update().get(pk=round_id)
            if game_round.finished_at or timezone.now() < game_round.ends_at:
                return
            was_open = game_round.status == GameRound.STATUS_OPEN
            if was_open:
                game_round.status = GameRound.STATUS_CLOSED
                game_round.save(update_fields=["status"])
        if was_open:
            send_room_event(game_round.room_id, "SUBMISSION_CLOSED", {"round": game_round.number})
        finish_round(game_round)
    except (GameRound.DoesNotExist, Room.DoesNotExist):
        pass
    finally:
        close_old_connections()


def score_rows(room):
    scores = {p.pk: 0 for p in room.players.all()}
    for game_round in room.rounds.filter(finished_at__isnull=False):
        submissions = list(game_round.submissions.select_related("player"))
        if not submissions:
            continue
        winner = min(submissions, key=lambda item: (abs(item.number - game_round.target), item.player_id))
        scores[winner.player_id] = scores.get(winner.player_id, 0) + 1
    return [{**player_data(p), "score": scores.get(p.pk, 0)} for p in room.players.all().order_by("id")]


def round_result_data(game_round):
    submissions = list(game_round.submissions.select_related("player"))
    winner = min(submissions, key=lambda item: (abs(item.number - game_round.target), item.player_id)) if submissions else None
    return {
        "round": game_round.number,
        "target": float(game_round.target),
        "winner": player_data(winner.player) if winner else None,
        "submissions": [{
            "player": player_data(item.player),
            "number": float(item.number),
            "distance": float(abs(item.number - game_round.target)),
            "won": bool(winner and item.player_id == winner.player_id),
        } for item in submissions],
    }


@transaction.atomic
def finish_round(game_round):
    game_round = GameRound.objects.select_for_update().select_related("room").get(pk=game_round.pk)
    if game_round.finished_at or game_round.status == GameRound.STATUS_FINISHED:
        return
    submissions = list(game_round.submissions.select_related("player"))
    game_round.finished_at = timezone.now()
    game_round.status = GameRound.STATUS_FINISHED
    game_round.save(update_fields=["finished_at", "status"])
    send_room_event(game_round.room_id, "ROUND_FINISHED", {"round": round_result_data(game_round)})
    room = game_round.room
    send_room_event(room.pk, "SCORE_UPDATED", {"players": score_rows(room)})
    if game_round.number >= TOTAL_ROUNDS:
        room.status = Room.STATUS_FINISHED
        room.save(update_fields=["status"])
        rows = score_rows(room)
        top = max((row["score"] for row in rows), default=0)
        winner_row = next((row for row in rows if row["score"] == top), None) if top else None
        send_room_event(room.pk, "GAME_FINISHED", {"winner": winner_row and {"id": winner_row["id"], "username": winner_row["username"]}})
    else:
        next_round = create_round(room, game_round.number + 1)
        send_room_event(room.pk, "ROUND_STARTED", {
            "round": next_round.number, "round_ends_at": next_round.ends_at.isoformat(),
        })


def create_round(room, number):
    duration = getattr(settings, "GAME_ROUND_SECONDS", 60)
    game_round = GameRound.objects.create(
        room=room, number=number,
        target=Decimal(str(round(random.uniform(0, 100), 2))),
        ends_at=timezone.now() + timedelta(seconds=duration),
    )
    transaction.on_commit(lambda: schedule_round_expiry(game_round.pk, game_round.ends_at))
    return game_round


@transaction.atomic
def start_game(room):
    room = Room.objects.select_for_update().get(pk=room.pk)
    if room.status != Room.STATUS_WAITING:
        return False, "La partie a déjà commencé."
    if room.players.count() < 2:
        return False, "Il faut au moins 2 joueurs pour démarrer."
    room.status = Room.STATUS_PLAYING
    room.starts_at = timezone.now()
    room.save(update_fields=["status", "starts_at"])
    first_round = create_round(room, 1)
    send_room_event(room.pk, "GAME_STARTED", {"starts_at": room.starts_at.isoformat()})
    send_room_event(room.pk, "ROUND_STARTED", {
        "round": first_round.number, "round_ends_at": first_round.ends_at.isoformat(),
    })
    return True, room


@transaction.atomic
def submit_number(room, player, number):
    room = Room.objects.select_for_update().get(pk=room.pk)
    if room.status != Room.STATUS_PLAYING:
        return False, "La partie n’est pas en cours."
    if not room.players.filter(pk=player.pk).exists():
        return False, "Vous ne participez pas à cette partie."
    current = room.rounds.select_for_update().filter(finished_at__isnull=True).order_by("number").first()
    if current is None:
        return False, "Aucune manche n’est active."
    if timezone.now() >= current.ends_at:
        expire_round(current.pk)
        return False, "Le délai de soumission est terminé."
    submission, created = Submission.objects.get_or_create(round=current, player=player, defaults={"number": number})
    if not created:
        return False, "Vous avez déjà soumis un nombre pour cette manche."
    send_room_event(room.pk, "NUMBER_SUBMITTED", {"player": player_data(player)})
    if current.submissions.count() >= room.players.count():
        current.status = GameRound.STATUS_CLOSED
        current.save(update_fields=["status"])
        send_room_event(room.pk, "SUBMISSION_CLOSED", {"round": current.number})
        finish_round(current)
    return True, {"round": current.number}


def close_expired_round(room):
    if room.status != Room.STATUS_PLAYING:
        return
    current = room.rounds.filter(finished_at__isnull=True).order_by("number").first()
    if current and timezone.now() >= current.ends_at:
        expire_round(current.pk)


def game_state(room, player):
    close_expired_round(room)
    room.refresh_from_db()
    current = room.rounds.filter(finished_at__isnull=True).order_by("number").first()
    latest = current or room.rounds.order_by("-number").first()
    previous = room.rounds.filter(finished_at__isnull=False).order_by("-number").first()
    round_status = latest.status if latest else GameRound.STATUS_CLOSED
    return {
        "status": room.status,
        "round": latest.number if latest else 0,
        "round_status": round_status,
        "total_rounds": TOTAL_ROUNDS,
        "round_ends_at": latest.ends_at.isoformat() if latest and current else None,
        "has_submitted": bool(current and current.submissions.filter(player=player).exists()),
        "players": score_rows(room),
        "last_round": ({
            "server_time": timezone.now().isoformat(),
            "round": round_result_data(previous),
        } if previous else None),
    }


def game_result(room):
    rows = sorted(score_rows(room), key=lambda row: (-row["score"], row["id"]))
    top = rows[0]["score"] if rows else 0
    winner = next(({"id": row["id"], "username": row["username"]} for row in rows if row["score"] == top), None) if top else None
    rounds = []
    for game_round in room.rounds.filter(finished_at__isnull=False).prefetch_related("submissions__player"):
        rounds.append(round_result_data(game_round))
    return {"winner": winner, "players": rows, "rounds": rounds}
