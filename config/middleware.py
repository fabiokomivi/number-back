from urllib.parse import parse_qs

from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, AuthenticationFailed
from rest_framework_simplejwt.exceptions import TokenError


@database_sync_to_async
def get_user_from_token(token):
    """
    Vérifie le JWT et récupère l'utilisateur correspondant.
    """
    jwt_auth = JWTAuthentication()

    validated_token = jwt_auth.get_validated_token(token.encode("utf-8"))

    return jwt_auth.get_user(validated_token)


class JWTAuthMiddleware(BaseMiddleware):

    async def __call__(self, scope, receive, send):

        # Récupérer le token dans les paramètres de l'URL
        query_string = scope.get("query_string", b"").decode()

        query_params = parse_qs(query_string)

        token = query_params.get("token", [None])[0]

        # Par défaut, utilisateur anonyme
        scope = dict(scope)
        scope["user"] = AnonymousUser()

        if token:
            try:
                scope["user"] = await get_user_from_token(token)

            except (InvalidToken, TokenError, AuthenticationFailed):
                scope["user"] = AnonymousUser()

        return await super().__call__(scope, receive, send)