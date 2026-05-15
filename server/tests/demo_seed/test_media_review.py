from __future__ import annotations

from pathlib import Path

from src.demo_seed.media.cache_index import CacheIndex, CachedMediaItem
from src.demo_seed.media.review_html import generate_media_review_html


def test_media_review_handles_missing_files(tmp_path: Path) -> None:
    index = CacheIndex(
        items=[
            CachedMediaItem(
                media_id="1",
                provider="pixabay",
                provider_item_id="42",
                media_type="image",
                topic="backend",
                role="post_media",
                query="server room",
                local_path=str(tmp_path / "missing.jpg"),
                width=800,
                height=600,
                duration_seconds=None,
                orientation="landscape",
                size_bytes=0,
                source_url="https://example.com",
                metadata={},
            )
        ]
    )
    output = generate_media_review_html(index, tmp_path / "review.html")
    assert output.exists()
    html = output.read_text(encoding="utf-8")
    assert "missing" in html
