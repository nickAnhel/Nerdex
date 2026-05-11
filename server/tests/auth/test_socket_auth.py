import uuid

import pytest
from jwt import InvalidTokenError

from src.auth import socket as socket_auth
from src.auth.socket import SocketAuthenticationError, authenticate_socket_user
from src.auth.utils import ACCESS_TOKEN_TYPE, REFRESH_TOKEN_TYPE
from src.users.exceptions import UserNotFound
from src.users.schemas import UserGet


class FakeUserService:
    def __init__(self, user: UserGet | None = None) -> None:
        self.user = user
        self.requested_user_id = None

    async def get_user(self, **filters):
        self.requested_user_id = filters.get("user_id")
        if self.user is None:
            raise UserNotFound("not found")

        return self.user


@pytest.mark.asyncio
async def test_authenticate_socket_user_returns_user_from_access_token(monkeypatch: pytest.MonkeyPatch) -> None:
    user_id = uuid.uuid4()
    user = UserGet(
        user_id=user_id,
        username="alice",
        is_admin=False,
        subscribers_count=0,
    )
    service = FakeUserService(user=user)
    monkeypatch.setattr(
        socket_auth,
        "decode_jwt",
        lambda token: {"type": ACCESS_TOKEN_TYPE, "sub": str(user_id)},
    )

    result = await authenticate_socket_user(
        auth={"token": "token-value"},
        user_service=service,  # type: ignore[arg-type]
    )

    assert result == user
    assert service.requested_user_id == str(user_id)


@pytest.mark.asyncio
async def test_authenticate_socket_user_rejects_missing_token() -> None:
    with pytest.raises(SocketAuthenticationError):
        await authenticate_socket_user(
            auth={},
            user_service=FakeUserService(),  # type: ignore[arg-type]
        )


@pytest.mark.asyncio
async def test_authenticate_socket_user_rejects_invalid_token(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_invalid_token(token: str):
        raise InvalidTokenError

    monkeypatch.setattr(socket_auth, "decode_jwt", raise_invalid_token)

    with pytest.raises(SocketAuthenticationError):
        await authenticate_socket_user(
            auth={"token": "bad-token"},
            user_service=FakeUserService(),  # type: ignore[arg-type]
        )


@pytest.mark.asyncio
async def test_authenticate_socket_user_rejects_refresh_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        socket_auth,
        "decode_jwt",
        lambda token: {"type": REFRESH_TOKEN_TYPE, "sub": str(uuid.uuid4())},
    )

    with pytest.raises(SocketAuthenticationError):
        await authenticate_socket_user(
            auth={"token": "refresh-token"},
            user_service=FakeUserService(),  # type: ignore[arg-type]
        )
