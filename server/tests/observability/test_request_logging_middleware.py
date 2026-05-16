import uuid

import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from src.observability.middleware import request_logging_middleware


def _build_request(*, path: str = "/ping", query_string: bytes = b"", headers: list[tuple[bytes, bytes]] | None = None) -> Request:
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": query_string,
        "headers": headers or [(b"host", b"test")],
        "client": ("127.0.0.1", 12345),
        "server": ("test", 80),
    }

    async def receive() -> dict:
        return {"type": "http.request", "body": b"", "more_body": False}

    return Request(scope, receive)


async def _call_next(request: Request) -> Response:
    return JSONResponse({"request_id": str(request.state.request_id)})


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_request_id_is_forwarded_from_header() -> None:
    request_id = "external-request-id"
    request = _build_request(headers=[(b"host", b"test"), (b"x-request-id", request_id.encode())])

    response = await request_logging_middleware(request, _call_next)

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == request_id


@pytest.mark.anyio
async def test_request_id_is_generated_when_missing() -> None:
    request = _build_request()

    response = await request_logging_middleware(request, _call_next)

    assert response.status_code == 200
    generated_id = response.headers.get("X-Request-ID")
    assert generated_id is not None
    uuid.UUID(generated_id)
