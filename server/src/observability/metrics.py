from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram


http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    labelnames=("method", "path", "status_code"),
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration",
    labelnames=("method", "path", "status_code"),
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10),
)

http_requests_in_progress = Gauge(
    "http_requests_in_progress",
    "In-progress HTTP requests",
    labelnames=("method", "path"),
)

recommendations_feed_duration_seconds = Histogram(
    "recommendations_feed_duration_seconds",
    "Recommendations feed duration",
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10),
)

recommendations_similar_duration_seconds = Histogram(
    "recommendations_similar_duration_seconds",
    "Similar content recommendations duration",
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10),
)

recommendations_authors_duration_seconds = Histogram(
    "recommendations_authors_duration_seconds",
    "Recommended authors duration",
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10),
)

recommendations_sync_duration_seconds = Histogram(
    "recommendations_sync_duration_seconds",
    "Recommendation sync duration",
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60, 180),
)

recommendations_feed_neo4j_duration_seconds = Histogram(
    "recommendations_feed_neo4j_duration_seconds",
    "Recommendation feed Neo4j query duration",
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5),
)

recommendations_feed_postgres_duration_seconds = Histogram(
    "recommendations_feed_postgres_duration_seconds",
    "Recommendation feed Postgres hydration duration",
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5),
)


def observe_http_request(*, method: str, path: str, status_code: int, duration_seconds: float) -> None:
    status_code_label = str(status_code)
    http_requests_total.labels(method=method, path=path, status_code=status_code_label).inc()
    http_request_duration_seconds.labels(
        method=method,
        path=path,
        status_code=status_code_label,
    ).observe(duration_seconds)


def observe_recommendations_feed(
    *,
    total_seconds: float,
    neo4j_seconds: float,
    postgres_seconds: float,
) -> None:
    recommendations_feed_duration_seconds.observe(total_seconds)
    recommendations_feed_neo4j_duration_seconds.observe(neo4j_seconds)
    recommendations_feed_postgres_duration_seconds.observe(postgres_seconds)


def observe_recommendations_similar(*, total_seconds: float) -> None:
    recommendations_similar_duration_seconds.observe(total_seconds)


def observe_recommendations_authors(*, total_seconds: float) -> None:
    recommendations_authors_duration_seconds.observe(total_seconds)


def observe_recommendations_sync(*, total_seconds: float) -> None:
    recommendations_sync_duration_seconds.observe(total_seconds)
