from typing import Any, Protocol

from jwt import InvalidTokenError

from src.auth.utils import ACCESS_TOKEN_TYPE, decode_jwt
from src.users.exceptions import UserNotFound
from src.users.schemas import UserGet


class SocketAuthenticationError(Exception):
    """Raised when a Socket.IO client cannot be authenticated."""


class SocketUserService(Protocol):
    async def get_user(self, **filters: Any) -> UserGet:
        ...


def _extract_socket_token(auth: Any) -> str:
    if not isinstance(auth, dict):
        raise SocketAuthenticationError("Missing authorization token")

    token = auth.get("token")
    if not isinstance(token, str) or not token:
        raise SocketAuthenticationError("Missing authorization token")

    if token.lower().startswith("bearer "):
        return token[7:]

    return token


async def authenticate_socket_user(
    *,
    auth: Any,
    user_service: SocketUserService,
) -> UserGet:
    token = _extract_socket_token(auth)

    try:
        payload = decode_jwt(token)
    except InvalidTokenError as exc:
        raise SocketAuthenticationError("Invalid authorization token") from exc

    if payload.get("type") != ACCESS_TOKEN_TYPE:
        raise SocketAuthenticationError("Invalid authorization token")

    try:
        user = await user_service.get_user(user_id=payload.get("sub"))
    except UserNotFound as exc:
        raise SocketAuthenticationError("Invalid authorization token") from exc

    return user
