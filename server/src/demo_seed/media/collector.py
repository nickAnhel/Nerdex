from __future__ import annotations

import hashlib
from pathlib import Path

from src.demo_seed.loaders.models import MediaQueriesEnvelope, TopicsConfig
from src.demo_seed.logging import get_logger
from src.demo_seed.media.cache_index import CacheIndex, CachedMediaItem, load_cache_index, save_cache_index
from src.demo_seed.media.pixabay_client import MediaDownloadError, PixabayClient


logger = get_logger(__name__)


ROLE_IMAGE = {"post_media", "article_covers", "video_covers", "avatars"}
ROLE_VIDEO = {"video_sources", "moment_sources"}


def _orientation(width: int, height: int) -> str:
    if width > height:
        return "landscape"
    if width < height:
        return "portrait"
    return "square"


def collect_media(
    *,
    client: PixabayClient,
    media_queries: MediaQueriesEnvelope,
    topics: TopicsConfig,
    cache_dir: Path,
    cache_index_path: Path,
    cache_budget_bytes: int,
) -> CacheIndex:
    cache_index = load_cache_index(cache_index_path)
    known_keys = {(item.provider_item_id, item.role): item for item in cache_index.items}

    defaults = media_queries.defaults
    image_defaults = defaults.get("images") or {}
    video_defaults = defaults.get("videos") or {}
    moment_defaults = defaults.get("moments") or {}

    role_targets = {
        "post_media": 24,
        "article_covers": 16,
        "video_covers": 12,
        "video_sources": 12,
        "moment_sources": 8,
        "avatars": 4,
    }

    for topic_slug, topic in topics.topics.items():
        topic_queries = media_queries.topics.get(topic_slug)
        if topic_queries is None:
            continue

        for role, target in role_targets.items():
            if cache_index.total_size_bytes >= cache_budget_bytes:
                logger.warning("Cache budget reached, stopping collection")
                save_cache_index(cache_index_path, cache_index)
                return cache_index

            existing = [item for item in cache_index.items if item.topic == topic_slug and item.role == role]
            needed = max(0, target - len(existing))
            if needed <= 0:
                continue

            if role in ROLE_IMAGE:
                queries = topic_queries.image_queries[:]
                per_page = int(image_defaults.get("per_page", 40))
                for query in queries:
                    hits = client.search_images(
                        query=query,
                        categories=topic_queries.categories,
                        safesearch=bool(defaults.get("safesearch", True)),
                        per_page=per_page,
                    )
                    for hit in hits:
                        key = (hit.item_id, role)
                        if key in known_keys:
                            continue
                        ext = "jpg"
                        local_name = f"{topic_slug}_{role}_{hit.item_id}.{ext}"
                        local_path = cache_dir / topic_slug / role / local_name
                        try:
                            size = client.download_file(
                                url=hit.download_url,
                                dest_path=local_path,
                                fallback_urls=hit.fallback_urls,
                            )
                        except MediaDownloadError:
                            logger.warning(
                                "Skipping image (download failed): topic=%s role=%s query=%s provider_id=%s",
                                topic_slug,
                                role,
                                query,
                                hit.item_id,
                            )
                            continue
                        item = CachedMediaItem(
                            media_id=hashlib.sha256(f"{topic_slug}:{role}:{hit.item_id}".encode()).hexdigest()[:24],
                            provider=media_queries.provider,
                            provider_item_id=hit.item_id,
                            media_type="image",
                            topic=topic_slug,
                            role=role,
                            query=query,
                            local_path=str(local_path),
                            width=hit.width,
                            height=hit.height,
                            duration_seconds=None,
                            orientation=_orientation(hit.width, hit.height),
                            size_bytes=size,
                            source_url=hit.download_url,
                            metadata={"preview_url": hit.preview_url},
                        )
                        cache_index.add(item)
                        known_keys[key] = item
                        needed -= 1
                        if needed <= 0:
                            break
                    if needed <= 0:
                        break
            else:
                queries = topic_queries.video_queries if role == "video_sources" else topic_queries.moment_queries
                defaults_for_role = video_defaults if role == "video_sources" else moment_defaults
                preferred_renditions = list(defaults_for_role.get("preferred_renditions") or ["small", "tiny"])
                forbidden_renditions = list(defaults_for_role.get("forbidden_renditions") or ["medium", "large"])
                max_duration_seconds = int(defaults_for_role.get("max_duration_seconds", 120))
                per_page = int(defaults_for_role.get("per_page", 20))
                for query in queries:
                    hits = client.search_videos(
                        query=query,
                        categories=topic_queries.categories,
                        safesearch=bool(defaults.get("safesearch", True)),
                        per_page=per_page,
                        preferred_renditions=preferred_renditions,
                        forbidden_renditions=forbidden_renditions,
                    )
                    for hit in hits:
                        if hit.duration > max_duration_seconds:
                            continue
                        if role == "moment_sources" and hit.height <= hit.width:
                            continue
                        key = (f"{hit.item_id}:{hit.rendition}", role)
                        if key in known_keys:
                            continue
                        local_name = f"{topic_slug}_{role}_{hit.item_id}_{hit.rendition}.mp4"
                        local_path = cache_dir / topic_slug / role / local_name
                        try:
                            size = client.download_file(
                                url=hit.download_url,
                                dest_path=local_path,
                                fallback_urls=hit.fallback_urls,
                            )
                        except MediaDownloadError:
                            logger.warning(
                                "Skipping video (download failed): topic=%s role=%s query=%s provider_id=%s rendition=%s",
                                topic_slug,
                                role,
                                query,
                                hit.item_id,
                                hit.rendition,
                            )
                            continue
                        item = CachedMediaItem(
                            media_id=hashlib.sha256(f"{topic_slug}:{role}:{hit.item_id}:{hit.rendition}".encode()).hexdigest()[:24],
                            provider=media_queries.provider,
                            provider_item_id=f"{hit.item_id}:{hit.rendition}",
                            media_type="video",
                            topic=topic_slug,
                            role=role,
                            query=query,
                            local_path=str(local_path),
                            width=hit.width,
                            height=hit.height,
                            duration_seconds=hit.duration,
                            orientation=_orientation(hit.width, hit.height),
                            size_bytes=size,
                            source_url=hit.download_url,
                            metadata={"rendition": hit.rendition},
                        )
                        cache_index.add(item)
                        known_keys[key] = item
                        needed -= 1
                        if needed <= 0:
                            break
                    if needed <= 0:
                        break

    save_cache_index(cache_index_path, cache_index)
    return cache_index
