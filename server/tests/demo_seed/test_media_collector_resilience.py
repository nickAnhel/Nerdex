from __future__ import annotations

from pathlib import Path

from src.demo_seed.loaders.models import MediaQueriesEnvelope, MediaTopicQueries, TopicDefinition, TopicTag, TopicsConfig
from src.demo_seed.media.cache_index import load_cache_index
from src.demo_seed.media.collector import collect_media
from src.demo_seed.media.pixabay_client import MediaDownloadError, PixabayImageHit


class FailingClient:
    def search_images(self, *, query: str, categories: list[str], safesearch: bool, per_page: int):
        return [
            PixabayImageHit(
                item_id="123",
                preview_url="https://example.com/preview.jpg",
                download_url="https://example.com/image.jpg",
                width=640,
                height=360,
                size_bytes=100,
                fallback_urls=[],
            )
        ]

    def search_videos(self, **kwargs):
        return []

    def download_file(self, *, url: str, dest_path: Path, fallback_urls: list[str] | None = None) -> int:
        raise MediaDownloadError("403")


def test_collect_media_skips_failed_downloads(tmp_path: Path) -> None:
    topics = TopicsConfig(
        version=1,
        topics={
            "backend": TopicDefinition(
                slug="backend",
                title="Backend",
                description="",
                weight=1.0,
                tags=[TopicTag(slug="fastapi", title="FastAPI", weight=1.0)],
                adjacent_topics={},
                content_angles=["service layer"],
            )
        },
    )
    media_queries = MediaQueriesEnvelope(
        version=1,
        provider="pixabay",
        defaults={"safesearch": True, "images": {"per_page": 1}, "videos": {}, "moments": {}},
        topics={
            "backend": MediaTopicQueries(
                categories=["computer"],
                image_queries=["server room"],
                video_queries=[],
                moment_queries=[],
                generated_cover_keywords=[],
                negative_keywords=[],
            )
        },
    )

    cache_index_path = tmp_path / "cache_index.json"
    cache = collect_media(
        client=FailingClient(),
        media_queries=media_queries,
        topics=topics,
        cache_dir=tmp_path / "cache",
        cache_index_path=cache_index_path,
        cache_budget_bytes=10_000_000,
    )

    assert cache.items == []
    stored = load_cache_index(cache_index_path)
    assert stored.items == []
