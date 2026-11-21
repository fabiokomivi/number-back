from django.urls import path

from .websockets import RoomConsumer

websocket_urlpatterns = [
    path("ws/rooms/<int:room_id>/", RoomConsumer.as_asgi()),
]
