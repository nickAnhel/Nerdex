from __future__ import annotations

import asyncio
import datetime as dt
import os
from dataclasses import asdict
from pathlib import Path

from sqlalchemy import select

from src.assets.enums import AttachmentTypeEnum
from src.assets.models import AssetModel
from src.assets.storage import AssetStorage
from src.common.database import async_session_maker
from src.content.enums import ContentTypeEnum
from src.content.models import ContentModel
from src.demo_seed.context import SeedRunContext
from src.demo_seed.generators.activity import build_activity_events
from src.demo_seed.generators.chats import build_chats
from src.demo_seed.generators.content import build_content
from src.demo_seed.generators.interactions import build_comment_reactions, build_comments, build_content_reactions
from src.demo_seed.generators.messages import build_messages
from src.demo_seed.generators.subscriptions import build_subscriptions
from src.demo_seed.generators.tags import collect_tag_slugs
from src.demo_seed.generators.users import build_users
from src.demo_seed.generators.views import build_view_sessions
from src.demo_seed.loaders.featured_users_loader import load_featured_users
from src.demo_seed.loaders.media_queries_loader import load_media_queries
from src.demo_seed.loaders.topics_loader import load_topics
from src.demo_seed.logging import get_logger
from src.demo_seed.media.cache_index import load_cache_index, save_cache_index
from src.demo_seed.media.collector import collect_media
from src.demo_seed.media.pixabay_client import PixabayClient
from src.demo_seed.media.review_html import generate_media_review_html
from src.demo_seed.planning.time_distribution import TimeDistributor
from src.demo_seed.reports.accounts_report import build_accounts_report
from src.demo_seed.reports.interests_report import build_expected_interests_report
from src.demo_seed.reports.manifest_report import build_manifest_report
from src.demo_seed.reports.seed_report import build_seed_report
from src.demo_seed.writers.seed_bulk_repository import SeedBulkRepository
from src.demo_seed.writers.seed_cleanup_repository import SeedCleanupRepository
from src.demo_seed.writers.seed_report_repository import write_json_report


logger = get_logger(__name__)


def _rows_users(users):
    rows = []
    for user in users:
        rows.append(
            {
                "user_id": user.user_id,
                "username": user.username,
                "display_name": user.display_name,
                "bio": user.bio,
                "links": user.links,
                "hashed_password": user.hashed_password,
                "is_admin": user.is_admin,
            }
        )
    return rows


def _rows_assets(assets):
    asset_rows = []
    variant_rows = []
    for asset in assets:
        asset_rows.append(
            {
                "asset_id": asset.asset_id,
                "owner_id": asset.owner_id,
                "asset_type": asset.asset_type,
                "original_filename": asset.original_filename,
                "original_extension": asset.original_extension,
                "declared_mime_type": asset.declared_mime_type,
                "detected_mime_type": asset.detected_mime_type,
                "size_bytes": asset.size_bytes,
                "status": asset.status,
                "access_type": asset.access_type,
                "asset_metadata": asset.asset_metadata,
                "created_at": asset.created_at,
                "updated_at": asset.updated_at,
            }
        )
        for variant in asset.variants:
            variant_rows.append(
                {
                    "asset_variant_id": variant.asset_variant_id,
                    "asset_id": asset.asset_id,
                    "asset_variant_type": variant.asset_variant_type,
                    "storage_bucket": variant.storage_bucket,
                    "storage_key": variant.storage_key,
                    "mime_type": variant.mime_type,
                    "size_bytes": variant.size_bytes,
                    "width": variant.width,
                    "height": variant.height,
                    "duration_ms": variant.duration_ms,
                    "bitrate": variant.bitrate,
                    "checksum_sha256": variant.checksum_sha256,
                    "is_primary": variant.is_primary,
                    "status": variant.status,
                    "variant_metadata": variant.variant_metadata,
                }
            )
    return asset_rows, variant_rows


def _rows_content(contents, tag_map):
    content_rows = []
    post_rows = []
    article_rows = []
    video_rows = []
    moment_rows = []
    playback_rows = []
    tag_rows = []
    content_asset_rows = []

    for content in contents:
        content_rows.append(
            {
                "content_id": content.content_id,
                "author_id": content.author_id,
                "content_type": content.content_type,
                "status": content.status,
                "visibility": content.visibility,
                "title": content.title,
                "excerpt": content.excerpt,
                "created_at": content.created_at,
                "updated_at": content.updated_at,
                "published_at": content.published_at,
                "content_metadata": content.content_metadata,
            }
        )

        if content.content_type == ContentTypeEnum.POST:
            post_rows.append(
                {
                    "content_id": content.content_id,
                    "body_text": content.body_text or "",
                }
            )
        elif content.content_type == ContentTypeEnum.ARTICLE:
            article_rows.append(
                {
                    "content_id": content.content_id,
                    "slug": content.slug or f"article-{content.content_id.hex[:8]}",
                    "body_markdown": content.body_markdown or "",
                    "word_count": content.word_count or 0,
                    "reading_time_minutes": content.reading_time_minutes or 1,
                    "toc": content.toc or [],
                }
            )
        elif content.content_type == ContentTypeEnum.VIDEO:
            video_rows.append(
                {
                    "content_id": content.content_id,
                    "description": content.description or "",
                    "chapters": content.chapters or [],
                    "publish_requested_at": content.published_at,
                    "created_at": content.created_at,
                    "updated_at": content.updated_at,
                }
            )
            playback_rows.append(
                {
                    "content_id": content.content_id,
                    "duration_seconds": content.playback_duration_seconds,
                    "width": content.playback_width,
                    "height": content.playback_height,
                    "orientation": content.playback_orientation,
                    "processing_status": content.playback_status,
                    "processing_error": None,
                    "available_quality_metadata": {"seed": True},
                    "created_at": content.created_at,
                    "updated_at": content.updated_at,
                }
            )
        elif content.content_type == ContentTypeEnum.MOMENT:
            moment_rows.append(
                {
                    "content_id": content.content_id,
                    "caption": content.caption or "",
                    "publish_requested_at": content.published_at,
                    "created_at": content.created_at,
                    "updated_at": content.updated_at,
                }
            )
            playback_rows.append(
                {
                    "content_id": content.content_id,
                    "duration_seconds": content.playback_duration_seconds,
                    "width": content.playback_width,
                    "height": content.playback_height,
                    "orientation": content.playback_orientation,
                    "processing_status": content.playback_status,
                    "processing_error": None,
                    "available_quality_metadata": {"seed": True},
                    "created_at": content.created_at,
                    "updated_at": content.updated_at,
                }
            )

        for tag_slug in content.tags:
            tag_id = tag_map.get(tag_slug)
            if tag_id is None:
                continue
            tag_rows.append({"content_id": content.content_id, "tag_id": tag_id})

        position = 0
        for asset_id in content.media_asset_ids:
            content_asset_rows.append(
                {
                    "content_id": content.content_id,
                    "asset_id": asset_id,
                    "attachment_type": AttachmentTypeEnum.MEDIA.value,
                    "position": position,
                    "placement_key": None,
                    "link_metadata": {"seed": True},
                    "created_at": content.created_at,
                }
            )
            position += 1

        if content.cover_asset_id:
            content_asset_rows.append(
                {
                    "content_id": content.content_id,
                    "asset_id": content.cover_asset_id,
                    "attachment_type": AttachmentTypeEnum.COVER.value,
                    "position": 0,
                    "placement_key": None,
                    "link_metadata": {"seed": True},
                    "created_at": content.created_at,
                }
            )

        for index, file_asset_id in enumerate(content.file_asset_ids):
            content_asset_rows.append(
                {
                    "content_id": content.content_id,
                    "asset_id": file_asset_id,
                    "attachment_type": AttachmentTypeEnum.FILE.value,
                    "position": index,
                    "placement_key": None,
                    "link_metadata": {"seed": True},
                    "created_at": content.created_at,
                }
            )

        if content.video_source_asset_id:
            content_asset_rows.append(
                {
                    "content_id": content.content_id,
                    "asset_id": content.video_source_asset_id,
                    "attachment_type": AttachmentTypeEnum.VIDEO_SOURCE.value,
                    "position": 0,
                    "placement_key": None,
                    "link_metadata": {"seed": True},
                    "created_at": content.created_at,
                }
            )

    return {
        "content": content_rows,
        "post": post_rows,
        "article": article_rows,
        "video": video_rows,
        "moment": moment_rows,
        "playback": playback_rows,
        "content_tags": tag_rows,
        "content_assets": content_asset_rows,
    }


async def _cleanup_seed_run(seed_run_id: str, storage: AssetStorage) -> dict[str, int]:
    async with async_session_maker() as session:
        cleanup_repo = SeedCleanupRepository(session)
        scope = await cleanup_repo.find_scope(seed_run_id)
        for bucket, key in scope.get("variant_keys", []):
            try:
                await storage.delete_object(bucket=bucket, key=key)
            except Exception:
                logger.warning("Failed to delete object %s/%s", bucket, key)
        counts = await cleanup_repo.cleanup_scope(scope)
        return counts


async def collect_media_command(context: SeedRunContext) -> dict:
    topics = load_topics(context.paths.data_dir / "topics.yaml")
    media_queries = load_media_queries(context.paths.data_dir / "media_queries.yaml")
    api_key = os.getenv("PIXABAY_API_KEY")
    if not api_key:
        raise RuntimeError("PIXABAY_API_KEY is required for media collection")
    client = PixabayClient(api_key=api_key)
    cache_index_path = context.paths.media_cache_dir / "cache_index.json"
    cache_index = collect_media(
        client=client,
        media_queries=media_queries,
        topics=topics,
        cache_dir=context.paths.media_cache_dir,
        cache_index_path=cache_index_path,
        cache_budget_bytes=context.media_config.cache_budget_bytes,
    )
    return {
        "items": len(cache_index.items),
        "cache_size_bytes": cache_index.total_size_bytes,
        "cache_index": str(cache_index_path),
    }


async def review_media_command(context: SeedRunContext) -> dict:
    cache_index_path = context.paths.media_cache_dir / "cache_index.json"
    cache_index = load_cache_index(cache_index_path)
    output_path = context.paths.output_dir / "media_review.html"
    generate_media_review_html(cache_index, output_path)
    return {
        "items": len(cache_index.items),
        "output": str(output_path),
    }


async def cleanup_command(seed_run_id: str) -> dict:
    storage = AssetStorage(__import__("src.config", fromlist=["settings"]).settings.storage)
    counts = await _cleanup_seed_run(seed_run_id, storage)
    return {"seed_run_id": seed_run_id, "deleted": counts}


async def run_seed_command(context: SeedRunContext, reset: bool) -> dict:
    topics = load_topics(context.paths.data_dir / "topics.yaml")
    featured_users = load_featured_users(context.paths.data_dir / "featured_users.yaml")
    media_queries = load_media_queries(context.paths.data_dir / "media_queries.yaml")

    storage_settings = __import__("src.config", fromlist=["settings"]).settings.storage
    storage = AssetStorage(storage_settings)

    if reset:
        logger.info("Reset requested. Cleaning previous demo runs discovered in content metadata.")
        async with async_session_maker() as session:
            seed_run_id_expr = ContentModel.content_metadata["seed_run_id"].as_string()
            run_ids_rows = await session.execute(
                select(seed_run_id_expr)
                .where(seed_run_id_expr.is_not(None))
                .distinct()
            )
            run_ids = [row[0] for row in run_ids_rows.all() if row[0]]
        for run_id in run_ids:
            logger.info("Reset: cleaning seed_run_id=%s", run_id)
            await _cleanup_seed_run(run_id, storage)
        logger.info("Reset: completed cleanup of %s run(s)", len(run_ids))

    # Ensure media cache exists. If empty, do collection first.
    cache_index_path = context.paths.media_cache_dir / "cache_index.json"
    cache_index = load_cache_index(cache_index_path)
    if not cache_index.items:
        logger.info("Media cache is empty, running collect phase before full seed.")
        await collect_media_command(context)
        cache_index = load_cache_index(cache_index_path)
    logger.info("Media cache ready: %s items (%s bytes)", len(cache_index.items), cache_index.total_size_bytes)

    distributor = TimeDistributor(context.random)

    users_result = await build_users(
        random=context.random,
        distributor=distributor,
        topics=topics,
        featured_users=featured_users,
        storage=storage,
        seed_run_id=context.seed_run_id,
        total_users=context.scale.users_total,
    )
    logger.info("Planning: users ready (%s)", len(users_result.users))

    content_result = await build_content(
        random=context.random,
        distributor=distributor,
        users=users_result.users,
        topics=topics,
        media_queries=media_queries,
        cache_index=cache_index,
        storage=storage,
        seed_run_id=context.seed_run_id,
        counts={
            "post": context.scale.posts,
            "article": context.scale.articles,
            "video": context.scale.videos,
            "moment": context.scale.moments,
        },
    )
    logger.info("Planning: content ready (%s)", len(content_result.contents))

    subscriptions = build_subscriptions(
        random=context.random,
        users=users_result.users,
        min_count=context.scale.subscriptions_min,
        max_count=context.scale.subscriptions_max,
    )
    logger.info("Planning: subscriptions ready (%s)", len(subscriptions))

    reactions = build_content_reactions(
        random=context.random,
        distributor=distributor,
        users=users_result.users,
        contents=content_result.contents,
        min_count=context.scale.content_reactions_min,
        max_count=context.scale.content_reactions_max,
    )
    logger.info("Planning: content reactions ready (%s)", len(reactions))
    comments = build_comments(
        random=context.random,
        distributor=distributor,
        users=users_result.users,
        contents=content_result.contents,
        min_count=context.scale.comments_min,
        max_count=context.scale.comments_max,
    )
    logger.info("Planning: comments ready (%s)", len(comments))
    comment_reactions = build_comment_reactions(
        random=context.random,
        distributor=distributor,
        users=users_result.users,
        comments=comments,
        min_count=context.scale.comment_reactions_min,
        max_count=context.scale.comment_reactions_max,
    )
    logger.info("Planning: comment reactions ready (%s)", len(comment_reactions))
    view_sessions = build_view_sessions(
        random=context.random,
        distributor=distributor,
        users=users_result.users,
        contents=content_result.contents,
        min_count=context.scale.view_sessions_min,
        max_count=context.scale.view_sessions_max,
    )
    logger.info("Planning: view sessions ready (%s)", len(view_sessions))

    contents_by_id = {content.content_id: content for content in content_result.contents}
    activity_events = build_activity_events(
        random=context.random,
        distributor=distributor,
        contents_by_id=contents_by_id,
        subscriptions=subscriptions,
        content_reactions=reactions,
        comments=comments,
        comment_reactions=comment_reactions,
        view_sessions=view_sessions,
        min_count=context.scale.activity_events_min,
        max_count=context.scale.activity_events_max,
        seed_run_id=context.seed_run_id,
    )
    logger.info("Planning: activity events ready (%s)", len(activity_events))

    chats_plan = build_chats(
        random=context.random,
        distributor=distributor,
        users=users_result.users,
        seed_run_id=context.seed_run_id,
        min_count=context.scale.chats_min,
        max_count=context.scale.chats_max,
    )
    logger.info(
        "Planning: chats ready (chats=%s memberships=%s events=%s)",
        len(chats_plan.chats),
        len(chats_plan.memberships),
        len(chats_plan.events),
    )

    file_asset_ids = [asset.asset_id for asset in content_result.assets if asset.asset_type.value == "file"]
    initial_seq_by_chat: dict = {}
    for item in chats_plan.timeline_items:
        initial_seq_by_chat[item.chat_id] = max(initial_seq_by_chat.get(item.chat_id, 0), item.chat_seq)
    messages_plan = build_messages(
        random=context.random,
        distributor=distributor,
        chats=chats_plan.chats,
        memberships=chats_plan.memberships,
        contents=content_result.contents,
        file_asset_ids=file_asset_ids,
        min_count=context.scale.messages_min,
        max_count=context.scale.messages_max,
        reactions_min=context.scale.message_reactions_min,
        reactions_max=context.scale.message_reactions_max,
        initial_seq_by_chat=initial_seq_by_chat,
    )
    logger.info(
        "Planning: messages ready (messages=%s reactions=%s shared=%s assets=%s)",
        len(messages_plan.messages),
        len(messages_plan.reactions),
        len(messages_plan.shared_content),
        len(messages_plan.message_assets),
    )

    all_assets = [*users_result.assets, *content_result.assets]
    content_rows = _rows_content(content_result.contents, tag_map={})

    async with async_session_maker() as session:
        repo = SeedBulkRepository(session)

        logger.info("Stage: users")
        await repo.insert_users(_rows_users(users_result.users))

        logger.info("Stage: assets")
        asset_rows, variant_rows = _rows_assets(all_assets)
        await repo.insert_assets(asset_rows)
        await repo.insert_asset_variants(variant_rows)
        for user in users_result.users:
            if user.avatar_asset_id:
                await repo.update_user_avatar(
                    user_id=user.user_id,
                    avatar_asset_id=user.avatar_asset_id,
                    avatar_crop={"x": 0.0, "y": 0.0, "size": 1.0},
                )

        logger.info("Stage: tags")
        tag_slugs = collect_tag_slugs(topics)
        tag_map = await repo.upsert_tags(tag_slugs)

        logger.info("Stage: content")
        content_rows = _rows_content(content_result.contents, tag_map=tag_map)
        await repo.insert_content(content_rows["content"])
        await repo.insert_post_details(content_rows["post"])
        await repo.insert_article_details(content_rows["article"])
        await repo.insert_video_details(content_rows["video"])
        await repo.insert_moment_details(content_rows["moment"])
        await repo.insert_video_playback_details(content_rows["playback"])
        await repo.insert_content_tags(content_rows["content_tags"])
        await repo.insert_content_assets(content_rows["content_assets"])

        logger.info("Stage: graph")
        await repo.insert_subscriptions([
            {"subscriber_id": row.subscriber_id, "subscribed_id": row.subscribed_id}
            for row in subscriptions
        ])

        logger.info("Stage: interactions")
        await repo.insert_content_reactions([
            {
                "content_id": row.content_id,
                "user_id": row.user_id,
                "reaction_type": row.reaction_type,
                "created_at": row.created_at,
            }
            for row in reactions
        ])
        await repo.insert_comments([
            {
                "comment_id": row.comment_id,
                "content_id": row.content_id,
                "author_id": row.author_id,
                "parent_comment_id": row.parent_comment_id,
                "root_comment_id": row.root_comment_id,
                "reply_to_comment_id": row.reply_to_comment_id,
                "depth": row.depth,
                "body_text": row.body_text,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
            }
            for row in comments
        ])
        await repo.insert_comment_reactions([
            {
                "comment_id": row.comment_id,
                "user_id": row.user_id,
                "reaction_type": row.reaction_type,
                "created_at": row.created_at,
            }
            for row in comment_reactions
        ])

        logger.info("Stage: views")
        await repo.insert_view_sessions([
            {
                "view_session_id": row.view_session_id,
                "content_id": row.content_id,
                "viewer_id": row.viewer_id,
                "anonymous_id": None,
                "started_at": row.started_at,
                "last_seen_at": row.last_seen_at,
                "last_position_seconds": row.last_position_seconds,
                "max_position_seconds": row.max_position_seconds,
                "watched_seconds": row.watched_seconds,
                "progress_percent": row.progress_percent,
                "is_counted": row.is_counted,
                "counted_at": row.counted_at,
                "counted_date": row.counted_date,
                "source": row.source,
                "view_metadata": row.view_metadata,
            }
            for row in view_sessions
        ])

        logger.info("Stage: activity")
        await repo.insert_activity_events([
            {
                "activity_event_id": row.activity_event_id,
                "user_id": row.user_id,
                "action_type": row.action_type,
                "content_id": row.content_id,
                "target_user_id": row.target_user_id,
                "comment_id": row.comment_id,
                "content_type": row.content_type,
                "event_metadata": row.event_metadata,
                "created_at": row.created_at,
            }
            for row in activity_events
        ])

        logger.info("Stage: chats")
        await repo.insert_chats([
            {
                "chat_id": row.chat_id,
                "title": row.title,
                "is_private": row.is_private,
                "chat_type": row.chat_type,
                "direct_key": row.direct_key,
                "owner_id": row.owner_id,
                "last_timeline_seq": 0,
            }
            for row in chats_plan.chats
        ])
        await repo.insert_memberships([
            {
                "chat_id": row.chat_id,
                "user_id": row.user_id,
                "role": row.role,
                "last_read_message_id": None,
                "is_muted": False,
            }
            for row in chats_plan.memberships
        ])

        logger.info("Stage: messages")
        await repo.insert_messages([
            {
                "message_id": row.message_id,
                "client_message_id": row.client_message_id,
                "content": row.content,
                "created_at": row.created_at,
                "reply_to_message_id": row.reply_to_message_id,
                "chat_id": row.chat_id,
                "user_id": row.user_id,
            }
            for row in messages_plan.messages
        ])
        await repo.insert_message_reactions([
            {
                "message_id": row.message_id,
                "user_id": row.user_id,
                "reaction_type": row.reaction_type,
                "created_at": row.created_at,
            }
            for row in messages_plan.reactions
        ])
        await repo.insert_message_shared_content([
            {
                "message_id": row.message_id,
                "content_id": row.content_id,
            }
            for row in messages_plan.shared_content
        ])
        await repo.insert_message_assets([
            {
                "message_id": row.message_id,
                "asset_id": row.asset_id,
                "sort_order": row.sort_order,
                "link_metadata": {"seed": True},
                "created_at": dt.datetime.now(dt.timezone.utc),
            }
            for row in messages_plan.message_assets
        ])

        logger.info("Stage: events/timeline")
        await repo.insert_events([
            {
                "event_id": row.event_id,
                "event_type": row.event_type,
                "created_at": row.created_at,
                "user_id": row.user_id,
                "altered_user_id": row.altered_user_id,
                "chat_id": row.chat_id,
            }
            for row in chats_plan.events
        ])
        await repo.insert_timeline_items([
            {
                "chat_id": row.chat_id,
                "chat_seq": row.chat_seq,
                "item_type": row.item_type,
                "message_id": row.message_id,
                "event_id": row.event_id,
            }
            for row in [*chats_plan.timeline_items, *messages_plan.timeline_items]
        ])

        logger.info("Stage: reconciliation")
        await repo.refresh_chat_last_sequence()
        await repo.reconcile_subscriber_counters()
        await repo.reconcile_comment_counters()
        await repo.reconcile_reaction_counters()
        await repo.reconcile_views_counters()

        await repo.commit()

    finished_at = dt.datetime.now(dt.timezone.utc)
    counts = {
        "users": len(users_result.users),
        "assets": len(all_assets),
        "content": len(content_result.contents),
        "subscriptions": len(subscriptions),
        "content_reactions": len(reactions),
        "comments": len(comments),
        "comment_reactions": len(comment_reactions),
        "view_sessions": len(view_sessions),
        "activity_events": len(activity_events),
        "chats": len(chats_plan.chats),
        "messages": len(messages_plan.messages),
        "message_reactions": len(messages_plan.reactions),
    }

    password_source = featured_users.defaults.get("password_env", "DEMO_SEED_USER_PASSWORD")
    accounts = build_accounts_report(users=users_result.users, password_source=password_source)
    expected_interests = build_expected_interests_report(users=users_result.users, contents=content_result.contents)

    manifest_items = []
    # manifest extracted from asset metadata for deterministic report
    for asset in all_assets:
        variant = asset.variants[0]
        manifest_items.append(
            {
                "seed_run_id": context.seed_run_id,
                "usage_target": asset.asset_metadata.get("usage_target"),
                "topic": asset.asset_metadata.get("topic"),
                "provider": asset.asset_metadata.get("provider"),
                "provider_item_id": asset.asset_metadata.get("provider_item_id"),
                "media_type": asset.asset_type.value,
                "local_path": asset.asset_metadata.get("local_path", "generated"),
                "s3_key": variant.storage_key,
                "metadata": {
                    "width": variant.width,
                    "height": variant.height,
                    "duration_ms": variant.duration_ms,
                    "mime_type": variant.mime_type,
                },
            }
        )

    report = build_seed_report(
        seed_run_id=context.seed_run_id,
        started_at=context.started_at,
        finished_at=finished_at,
        created_counts=counts,
        media_cache_size_bytes=cache_index.total_size_bytes,
        uploaded_objects=sum(len(asset.variants) for asset in all_assets),
        skipped_media=len([item for item in cache_index.items if not Path(item.local_path).exists()]),
        warnings=context.warnings,
        errors=context.errors,
    )

    write_json_report(context.paths.output_dir / "demo_accounts.json", accounts)
    write_json_report(context.paths.output_dir / "demo_expected_interests.json", {"users": expected_interests})
    write_json_report(context.paths.output_dir / "manifest_used.json", {"assets": manifest_items})
    write_json_report(context.paths.output_dir / "demo_seed_report.json", report)

    return report
