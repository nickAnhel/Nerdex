import pytest

from src.observability.router import metrics


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_metrics_endpoint_exposes_prometheus_metrics() -> None:
    response = await metrics()

    assert response.status_code == 200
    assert "text/plain" in response.media_type

    body = response.body.decode("utf-8")
    assert "http_requests_total" in body
    assert "http_request_duration_seconds" in body
    assert "recommendations_feed_duration_seconds" in body
