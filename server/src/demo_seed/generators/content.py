from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from src.assets.enums import AttachmentTypeEnum, AssetVariantTypeEnum
from src.assets.storage import AssetStorage
from src.content.enums import ContentStatusEnum, ContentTypeEnum, ContentVisibilityEnum
from src.demo_seed.generators.assets import SeedAssetBuilder
from src.demo_seed.loaders.models import MediaQueriesEnvelope, TopicsConfig
from src.demo_seed.logging import get_logger
from src.demo_seed.media.cache_index import CacheIndex, CachedMediaItem
from src.demo_seed.media.covers_generator import generate_technical_cover
from src.demo_seed.media.files_generator import generate_files
from src.demo_seed.planning.affinity import build_topic_weights_for_author, pick_tags_for_topic
from src.demo_seed.planning.plans import PlannedAsset, PlannedContent, PlannedUser
from src.demo_seed.planning.random_state import SeedRandom
from src.demo_seed.planning.text_plans import (
    build_article_text,
    build_moment_text,
    build_post_text,
    build_video_text,
)
from src.demo_seed.planning.time_distribution import TimeDistributor
from src.videos.enums import VideoOrientationEnum, VideoProcessingStatusEnum

logger = get_logger(__name__)


@dataclass(slots=True)
class ContentPlanResult:
    contents: list[PlannedContent] = field(default_factory=list)
    assets: list[PlannedAsset] = field(default_factory=list)


@dataclass(slots=True)
class AssetPools:
    by_role_topic: dict[str, dict[str, list[PlannedAsset]]] = field(default_factory=dict)
    generated_covers: dict[str, list[PlannedAsset]] = field(default_factory=dict)
    generated_files: list[PlannedAsset] = field(default_factory=list)


def _is_published_public(status: ContentStatusEnum, visibility: ContentVisibilityEnum) -> bool:
    return status == ContentStatusEnum.PUBLISHED and visibility == ContentVisibilityEnum.PUBLIC


def _pick_status_visibility(random: SeedRandom) -> tuple[ContentStatusEnum, ContentVisibilityEnum, dt.datetime | None]:
    ticket = random.random()
    now = dt.datetime.now(dt.timezone.utc)
    if ticket <= 0.86:
        return ContentStatusEnum.PUBLISHED, ContentVisibilityEnum.PUBLIC, now
    if ticket <= 0.93:
        return ContentStatusEnum.PUBLISHED, ContentVisibilityEnum.PRIVATE, now
    return ContentStatusEnum.DRAFT, ContentVisibilityEnum.PRIVATE, None


def _choose_author(random: SeedRandom, users: list[PlannedUser]) -> PlannedUser:
    weighted: list[tuple[PlannedUser, float]] = []
    for user in users:
        base = 0.6
        if user.role in {"active_author", "popular_author"}:
            base = 1.8
        elif user.role == "regular_user":
            base = 0.8
        weighted.append((user, base))
    return random.weighted_choice(weighted)


def _choose_topic_for_author(random: SeedRandom, user: PlannedUser, topics: TopicsConfig) -> str:
    weighted = build_topic_weights_for_author(user.interests, topics)
    return random.weighted_choice(weighted)


def _existing_file(item: CachedMediaItem) -> bool:
    return Path(item.local_path).exists()


async def _build_asset_pools(
    *,
    random: SeedRandom,
    users: list[PlannedUser],
    topics: TopicsConfig,
    media_queries: MediaQueriesEnvelope,
    cache_index: CacheIndex,
    storage: AssetStorage,
    seed_run_id: str,
) -> tuple[AssetPools, list[PlannedAsset]]:
    logger.info("Content assets: preparing upload pools from cache + generated assets")
    pools = AssetPools(by_role_topic={}, generated_covers={}, generated_files=[])
    all_assets: list[PlannedAsset] = []
    asset_builder = SeedAssetBuilder(storage=storage, seed_run_id=seed_run_id)

    # Upload cache media once and reuse in content links.
    uploaded_cache_assets = 0
    skipped_cache_assets = 0
    for item in cache_index.items:
        if not _existing_file(item):
            skipped_cache_assets += 1
            continue
        owner = random.choice(users)
        planned = await asset_builder.from_local_file(
            owner_id=owner.user_id,
            local_path=Path(item.local_path),
            key_suffix=f"media_cache/{item.topic}/{item.role}",
            usage_target=item.role,
            topic=item.topic,
            provider=item.provider,
            provider_item_id=item.provider_item_id,
            variant_type=AssetVariantTypeEnum.ORIGINAL,
            media_type_hint=item.media_type,
            width=item.width,
            height=item.height,
            duration_ms=(item.duration_seconds * 1000) if item.duration_seconds else None,
        )
        pools.by_role_topic.setdefault(item.role, {}).setdefault(item.topic, []).append(planned)
        all_assets.append(planned)
        uploaded_cache_assets += 1
        if uploaded_cache_assets % 25 == 0:
            logger.info("Content assets: uploaded %s media-cache assets", uploaded_cache_assets)

    # Generated technical covers (200-350 target).
    covers_target = 260
    logger.info("Content assets: generating %s technical covers", covers_target)
    for i in range(covers_target):
        owner = random.choice(users)
        topic_slug = random.choice(list(topics.topics.keys()))
        topic = topics.topics[topic_slug]
        keywords = media_queries.topics.get(topic_slug).generated_cover_keywords if media_queries.topics.get(topic_slug) else []
        angle = random.choice(topic.content_angles or [topic.title])
        cover = generate_technical_cover(topic=topic_slug, title=f"{topic.title} {i}", keywords=keywords or [angle])
        planned = await asset_builder.from_bytes(
            owner_id=owner.user_id,
            payload=cover.payload,
            filename=f"{topic_slug}_technical_cover_{i:04d}.jpg",
            mime_type=cover.mime_type,
            key_suffix=f"generated_covers/{topic_slug}",
            usage_target="generated_technical_cover",
            topic=topic_slug,
            provider="generated",
            provider_item_id=f"cover_{i}",
            width=cover.width,
            height=cover.height,
            variant_type=AssetVariantTypeEnum.ORIGINAL,
        )
        pools.generated_covers.setdefault(topic_slug, []).append(planned)
        all_assets.append(planned)
        if (i + 1) % 50 == 0:
            logger.info("Content assets: generated/uploaded covers %s/%s", i + 1, covers_target)

    # Generated file attachments (100-200 target).
    file_assets_target = 140
    logger.info("Content assets: generating %s file attachments", file_assets_target)
    generated_files = generate_files(random, file_assets_target)
    for index, generated in enumerate(generated_files):
        owner = random.choice(users)
        topic_slug = random.choice(list(topics.topics.keys()))
        planned = await asset_builder.from_bytes(
            owner_id=owner.user_id,
            payload=generated.payload,
            filename=generated.filename,
            mime_type=generated.mime_type,
            key_suffix=f"generated_files/{topic_slug}",
            usage_target="generated_file_attachment",
            topic=topic_slug,
            provider="generated",
            provider_item_id=f"file_{index}",
            variant_type=AssetVariantTypeEnum.ORIGINAL,
        )
        pools.generated_files.append(planned)
        all_assets.append(planned)
        if (index + 1) % 25 == 0:
            logger.info("Content assets: generated/uploaded files %s/%s", index + 1, file_assets_target)

    logger.info(
        "Content assets: completed (%s uploaded from cache, %s skipped missing, %s total assets)",
        uploaded_cache_assets,
        skipped_cache_assets,
        len(all_assets),
    )

    return pools, all_assets


def _pick_pool_asset(random: SeedRandom, pools: dict[str, dict[str, list[PlannedAsset]]], role: str, topic: str) -> PlannedAsset | None:
    by_topic = pools.get(role) or {}
    if by_topic.get(topic):
        return random.choice(by_topic[topic])
    fallback: list[PlannedAsset] = []
    for items in by_topic.values():
        fallback.extend(items)
    return random.choice(fallback) if fallback else None


def _pick_cover_asset(random: SeedRandom, cover_pool: dict[str, list[PlannedAsset]], topic: str) -> PlannedAsset | None:
    if cover_pool.get(topic):
        return random.choice(cover_pool[topic])
    all_items: list[PlannedAsset] = []
    for items in cover_pool.values():
        all_items.extend(items)
    return random.choice(all_items) if all_items else None


async def build_content(
    *,
    random: SeedRandom,
    distributor: TimeDistributor,
    users: list[PlannedUser],
    topics: TopicsConfig,
    media_queries: MediaQueriesEnvelope,
    cache_index: CacheIndex,
    storage: AssetStorage,
    seed_run_id: str,
    counts: dict[str, int],
) -> ContentPlanResult:
    logger.info(
        "Content: generating publications posts=%s articles=%s videos=%s moments=%s",
        counts["post"],
        counts["article"],
        counts["video"],
        counts["moment"],
    )
    pools, pool_assets = await _build_asset_pools(
        random=random,
        users=users,
        topics=topics,
        media_queries=media_queries,
        cache_index=cache_index,
        storage=storage,
        seed_run_id=seed_run_id,
    )

    contents: list[PlannedContent] = []

    def _common_content(content_type: ContentTypeEnum) -> tuple[PlannedUser, str, ContentStatusEnum, ContentVisibilityEnum, dt.datetime, dt.datetime | None, list[str], str]:
        author = _choose_author(random, users)
        topic_slug = _choose_topic_for_author(random, author, topics)
        topic = topics.topics[topic_slug]
        tags = pick_tags_for_topic(random, topic)
        angle = random.choice(topic.content_angles or [topic.title])

        created_at = distributor.random_content_created_at()
        status, visibility, published_at_seed = _pick_status_visibility(random)
        published_at = None
        if published_at_seed is not None:
            published_at = distributor.random_after(created_at, min_minutes=30, max_days=60)
        return author, topic_slug, status, visibility, created_at, published_at, tags, angle

    # Posts.
    for _ in range(counts["post"]):
        author, topic_slug, status, visibility, created_at, published_at, tags, angle = _common_content(ContentTypeEnum.POST)
        topic = topics.topics[topic_slug]
        title, excerpt, body = build_post_text(random, topic, angle, tags)
        media_ids: list[uuid.UUID] = []
        if random.random() <= 0.72:
            media_asset = _pick_pool_asset(random, pools.by_role_topic, "post_media", topic_slug)
            if media_asset:
                media_ids.append(media_asset.asset_id)

        contents.append(
            PlannedContent(
                content_id=uuid.uuid4(),
                author_id=author.user_id,
                content_type=ContentTypeEnum.POST,
                status=status,
                visibility=visibility,
                title=title,
                excerpt=excerpt,
                created_at=created_at,
                updated_at=created_at,
                published_at=published_at if status == ContentStatusEnum.PUBLISHED else None,
                content_metadata={"seed_run_id": seed_run_id, "topic": topic_slug, "is_demo": True},
                topic=topic_slug,
                tags=tags,
                media_asset_ids=media_ids,
                cover_asset_id=None,
                file_asset_ids=[],
                body_text=body,
            )
        )
        if len(contents) % 100 == 0:
            logger.info("Content: prepared %s total publications", len(contents))

    # Articles.
    for _ in range(counts["article"]):
        author, topic_slug, status, visibility, created_at, published_at, tags, angle = _common_content(ContentTypeEnum.ARTICLE)
        topic = topics.topics[topic_slug]
        title, excerpt, markdown, words, reading_minutes, toc, slug = build_article_text(random, topic, angle, tags)
        cover = _pick_cover_asset(random, pools.generated_covers, topic_slug)
        file_ids: list[uuid.UUID] = []
        if random.random() <= 0.45 and pools.generated_files:
            file_ids = [random.choice(pools.generated_files).asset_id]

        contents.append(
            PlannedContent(
                content_id=uuid.uuid4(),
                author_id=author.user_id,
                content_type=ContentTypeEnum.ARTICLE,
                status=status,
                visibility=visibility,
                title=title,
                excerpt=excerpt,
                created_at=created_at,
                updated_at=created_at,
                published_at=published_at if status == ContentStatusEnum.PUBLISHED else None,
                content_metadata={"seed_run_id": seed_run_id, "topic": topic_slug, "is_demo": True},
                topic=topic_slug,
                tags=tags,
                media_asset_ids=[],
                cover_asset_id=cover.asset_id if cover else None,
                file_asset_ids=file_ids,
                body_markdown=markdown,
                slug=f"{slug}-{uuid.uuid4().hex[:8]}",
                word_count=words,
                reading_time_minutes=reading_minutes,
                toc=toc,
            )
        )
        if len(contents) % 100 == 0:
            logger.info("Content: prepared %s total publications", len(contents))

    # Videos.
    for _ in range(counts["video"]):
        author, topic_slug, status, visibility, created_at, published_at, tags, angle = _common_content(ContentTypeEnum.VIDEO)
        topic = topics.topics[topic_slug]
        title, excerpt, description, chapters = build_video_text(random, topic, angle, tags)
        source_asset = _pick_pool_asset(random, pools.by_role_topic, "video_sources", topic_slug)
        cover_asset = _pick_cover_asset(random, pools.generated_covers, topic_slug) or _pick_pool_asset(random, pools.by_role_topic, "video_covers", topic_slug)

        duration = 60
        width = 720
        height = 406
        orientation = VideoOrientationEnum.LANDSCAPE
        if source_asset and source_asset.variants:
            variant = source_asset.variants[0]
            duration = max(10, int((variant.duration_ms or 60000) / 1000))
            width = variant.width or width
            height = variant.height or height
            if height > width:
                orientation = VideoOrientationEnum.PORTRAIT
            elif width == height:
                orientation = VideoOrientationEnum.SQUARE

        if not source_asset:
            source_asset = _pick_pool_asset(random, pools.by_role_topic, "moment_sources", topic_slug)

        final_status = status
        final_visibility = visibility
        if source_asset is None or cover_asset is None:
            final_status = ContentStatusEnum.DRAFT
            final_visibility = ContentVisibilityEnum.PRIVATE

        contents.append(
            PlannedContent(
                content_id=uuid.uuid4(),
                author_id=author.user_id,
                content_type=ContentTypeEnum.VIDEO,
                status=final_status,
                visibility=final_visibility,
                title=title,
                excerpt=excerpt,
                created_at=created_at,
                updated_at=created_at,
                published_at=published_at if _is_published_public(final_status, final_visibility) or final_status == ContentStatusEnum.PUBLISHED else None,
                content_metadata={"seed_run_id": seed_run_id, "topic": topic_slug, "is_demo": True},
                topic=topic_slug,
                tags=tags,
                media_asset_ids=[],
                cover_asset_id=cover_asset.asset_id if cover_asset else None,
                file_asset_ids=[],
                description=description,
                chapters=chapters,
                video_source_asset_id=source_asset.asset_id if source_asset else None,
                playback_duration_seconds=duration,
                playback_width=width,
                playback_height=height,
                playback_orientation=orientation,
                playback_status=VideoProcessingStatusEnum.READY,
            )
        )
        if len(contents) % 100 == 0:
            logger.info("Content: prepared %s total publications", len(contents))

    # Moments.
    for _ in range(counts["moment"]):
        author, topic_slug, status, visibility, created_at, published_at, tags, angle = _common_content(ContentTypeEnum.MOMENT)
        topic = topics.topics[topic_slug]
        title, excerpt, caption = build_moment_text(random, topic, angle, tags)
        source_asset = _pick_pool_asset(random, pools.by_role_topic, "moment_sources", topic_slug)
        if source_asset is None:
            source_asset = _pick_pool_asset(random, pools.by_role_topic, "video_sources", topic_slug)
        cover_asset = _pick_cover_asset(random, pools.generated_covers, topic_slug)

        duration = random.randint(15, 90)
        width = 720
        height = 1280
        if source_asset and source_asset.variants:
            variant = source_asset.variants[0]
            width = variant.width or width
            height = variant.height or height
            duration = min(90, max(8, int((variant.duration_ms or 45000) / 1000)))
        if width >= height:
            width, height = 720, 1280

        final_status = status
        final_visibility = visibility
        if source_asset is None or cover_asset is None:
            final_status = ContentStatusEnum.DRAFT
            final_visibility = ContentVisibilityEnum.PRIVATE

        contents.append(
            PlannedContent(
                content_id=uuid.uuid4(),
                author_id=author.user_id,
                content_type=ContentTypeEnum.MOMENT,
                status=final_status,
                visibility=final_visibility,
                title=title,
                excerpt=excerpt,
                created_at=created_at,
                updated_at=created_at,
                published_at=published_at if _is_published_public(final_status, final_visibility) or final_status == ContentStatusEnum.PUBLISHED else None,
                content_metadata={"seed_run_id": seed_run_id, "topic": topic_slug, "is_demo": True},
                topic=topic_slug,
                tags=tags,
                media_asset_ids=[],
                cover_asset_id=cover_asset.asset_id if cover_asset else None,
                file_asset_ids=[],
                caption=caption,
                video_source_asset_id=source_asset.asset_id if source_asset else None,
                playback_duration_seconds=duration,
                playback_width=width,
                playback_height=height,
                playback_orientation=VideoOrientationEnum.PORTRAIT,
                playback_status=VideoProcessingStatusEnum.READY,
            )
        )
        if len(contents) % 100 == 0:
            logger.info("Content: prepared %s total publications", len(contents))

    logger.info("Content: generation completed (%s publications)", len(contents))

    return ContentPlanResult(contents=contents, assets=pool_assets)
