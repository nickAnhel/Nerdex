from __future__ import annotations

import datetime
import uuid

from sqlalchemy import delete, desc, exists, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.assets.enums import AttachmentTypeEnum
from src.assets.models import AssetModel, ContentAssetModel
import src.tags.models  # noqa: F401
from src.content.enums import ContentStatusEnum, ContentTypeEnum, ContentVisibilityEnum, ReactionTypeEnum
from src.content.models import ContentModel, ContentReactionModel
from src.users.models import UserModel
from src.videos.enums import VideoOrder, VideoProcessingStatusEnum, VideoProfileFilter
from src.videos.models import VideoDetailsModel, VideoPlaybackDetailsModel


VIDEO_ATTACHMENT_TYPES = (
    AttachmentTypeEnum.VIDEO_SOURCE,
    AttachmentTypeEnum.COVER,
)


class VideoRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        author_id: uuid.UUID,
        title: str,
        excerpt: str,
        description: str,
        chapters: list[dict[str, object]],
        status: ContentStatusEnum,
        visibility: ContentVisibilityEnum,
        duration_seconds: int | None,
        width: int | None,
        height: int | None,
        orientation,
        processing_status: VideoProcessingStatusEnum,
        processing_error: str | None,
        available_quality_metadata: dict[str, object],
        publish_requested_at: datetime.datetime | None,
        created_at: datetime.datetime,
        updated_at: datetime.datetime,
        published_at: datetime.datetime | None,
        commit: bool = True,
    ) -> ContentModel:
        result = await self._session.execute(
            insert(ContentModel)
            .values(
                author_id=author_id,
                content_type=ContentTypeEnum.VIDEO,
                status=status,
                visibility=visibility,
                title=title,
                excerpt=excerpt,
                created_at=created_at,
                updated_at=updated_at,
                published_at=published_at,
            )
            .returning(ContentModel.content_id)
        )
        content_id = result.scalar_one()

        await self._session.execute(
            insert(VideoDetailsModel).values(
                content_id=content_id,
                description=description,
                chapters=chapters,
                publish_requested_at=publish_requested_at,
                created_at=created_at,
                updated_at=updated_at,
            )
        )
        await self._session.execute(
            insert(VideoPlaybackDetailsModel).values(
                content_id=content_id,
                duration_seconds=duration_seconds,
                width=width,
                height=height,
                orientation=orientation,
                processing_status=processing_status,
                processing_error=processing_error,
                available_quality_metadata=available_quality_metadata,
                created_at=created_at,
                updated_at=updated_at,
            )
        )
        if commit:
            await self._session.commit()
        else:
            await self._session.flush()
        return await self.get_single(content_id=content_id)

    async def get_single(
        self,
        *,
        content_id: uuid.UUID,
        viewer_id: uuid.UUID | None = None,
    ) -> ContentModel | None:
        stmt = self._build_video_query(viewer_id=viewer_id).where(ContentModel.content_id == content_id)
        result = await self._session.execute(stmt)
        return self._one_or_none(result, viewer_id=viewer_id)

    async def get_feed(
        self,
        *,
        viewer_id: uuid.UUID | None,
        order: VideoOrder,
        order_desc: bool,
        offset: int,
        limit: int,
    ) -> list[ContentModel]:
        stmt = (
            self._build_video_query(viewer_id=viewer_id)
            .join(VideoPlaybackDetailsModel)
            .where(ContentModel.status == ContentStatusEnum.PUBLISHED)
            .where(ContentModel.visibility == ContentVisibilityEnum.PUBLIC)
            .where(ContentModel.deleted_at.is_(None))
            .where(VideoPlaybackDetailsModel.processing_status == VideoProcessingStatusEnum.READY)
            .order_by(self._order_by_clause(order=order, order_desc=order_desc))
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return self._many(result, viewer_id=viewer_id)

    async def get_author_videos(
        self,
        *,
        author_id: uuid.UUID,
        viewer_id: uuid.UUID | None,
        profile_filter: VideoProfileFilter,
        order: VideoOrder,
        order_desc: bool,
        offset: int,
        limit: int,
    ) -> list[ContentModel]:
        stmt = (
            self._build_video_query(viewer_id=viewer_id)
            .where(ContentModel.author_id == author_id)
            .where(ContentModel.deleted_at.is_(None))
        )
        if viewer_id == author_id:
            if profile_filter == VideoProfileFilter.ALL:
                stmt = stmt.where(ContentModel.status.in_([ContentStatusEnum.PUBLISHED, ContentStatusEnum.DRAFT]))
            elif profile_filter == VideoProfileFilter.DRAFTS:
                stmt = stmt.where(ContentModel.status == ContentStatusEnum.DRAFT)
            elif profile_filter == VideoProfileFilter.PRIVATE:
                stmt = (
                    stmt.where(ContentModel.status == ContentStatusEnum.PUBLISHED)
                    .where(ContentModel.visibility == ContentVisibilityEnum.PRIVATE)
                )
            else:
                stmt = (
                    stmt.join(VideoPlaybackDetailsModel)
                    .where(ContentModel.status == ContentStatusEnum.PUBLISHED)
                    .where(ContentModel.visibility == ContentVisibilityEnum.PUBLIC)
                    .where(VideoPlaybackDetailsModel.processing_status == VideoProcessingStatusEnum.READY)
                )
        else:
            stmt = (
                stmt.join(VideoPlaybackDetailsModel)
                .where(ContentModel.status == ContentStatusEnum.PUBLISHED)
                .where(ContentModel.visibility == ContentVisibilityEnum.PUBLIC)
                .where(VideoPlaybackDetailsModel.processing_status == VideoProcessingStatusEnum.READY)
            )

        stmt = (
            stmt.order_by(self._order_by_clause(order=order, order_desc=order_desc))
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return self._many(result, viewer_id=viewer_id)

    async def update_video(
        self,
        *,
        content_id: uuid.UUID,
        title: str,
        excerpt: str,
        description: str,
        chapters: list[dict[str, object]],
        status: ContentStatusEnum,
        visibility: ContentVisibilityEnum,
        publish_requested_at: datetime.datetime | None,
        updated_at: datetime.datetime,
        published_at: datetime.datetime | None,
        processing_error: str | None = None,
        commit: bool = True,
    ) -> ContentModel:
        await self._session.execute(
            update(ContentModel)
            .where(ContentModel.content_id == content_id)
            .values(
                title=title,
                excerpt=excerpt,
                status=status,
                visibility=visibility,
                updated_at=updated_at,
                published_at=published_at,
            )
        )
        await self._session.execute(
            update(VideoDetailsModel)
            .where(VideoDetailsModel.content_id == content_id)
            .values(
                description=description,
                chapters=chapters,
                publish_requested_at=publish_requested_at,
                updated_at=updated_at,
            )
        )
        if processing_error is not None:
            await self._session.execute(
                update(VideoPlaybackDetailsModel)
                .where(VideoPlaybackDetailsModel.content_id == content_id)
                .values(processing_error=processing_error, updated_at=updated_at)
            )
        if commit:
            await self._session.commit()
        else:
            await self._session.flush()
        return await self.get_single(content_id=content_id)

    async def update_playback_details(
        self,
        *,
        content_id: uuid.UUID,
        duration_seconds: int | None,
        width: int | None,
        height: int | None,
        orientation,
        processing_status: VideoProcessingStatusEnum,
        processing_error: str | None,
        available_quality_metadata: dict[str, object],
        updated_at: datetime.datetime,
        commit: bool = True,
    ) -> None:
        await self._session.execute(
            update(VideoPlaybackDetailsModel)
            .where(VideoPlaybackDetailsModel.content_id == content_id)
            .values(
                duration_seconds=duration_seconds,
                width=width,
                height=height,
                orientation=orientation,
                processing_status=processing_status,
                processing_error=processing_error,
                available_quality_metadata=available_quality_metadata,
                updated_at=updated_at,
            )
        )
        if commit:
            await self._session.commit()
        else:
            await self._session.flush()

    async def replace_asset_links(
        self,
        *,
        content_id: uuid.UUID,
        attachments: list[dict[str, object]],
        commit: bool = True,
    ) -> None:
        await self._session.execute(
            delete(ContentAssetModel).where(
                ContentAssetModel.content_id == content_id,
                ContentAssetModel.attachment_type.in_(VIDEO_ATTACHMENT_TYPES),
            )
        )
        if attachments:
            await self._session.execute(
                insert(ContentAssetModel),
                [{**attachment, "content_id": content_id} for attachment in attachments],
            )
        if commit:
            await self._session.commit()
        else:
            await self._session.flush()

    async def get_attachment_asset_ids(self, *, content_id: uuid.UUID) -> set[uuid.UUID]:
        result = await self._session.execute(
            select(ContentAssetModel.asset_id).where(
                ContentAssetModel.content_id == content_id,
                ContentAssetModel.attachment_type.in_(VIDEO_ATTACHMENT_TYPES),
            )
        )
        return set(result.scalars().all())

    async def soft_delete_video(
        self,
        *,
        content_id: uuid.UUID,
        updated_at: datetime.datetime,
        deleted_at: datetime.datetime,
        commit: bool = True,
    ) -> None:
        await self._session.execute(
            update(ContentModel)
            .where(ContentModel.content_id == content_id)
            .values(
                status=ContentStatusEnum.DELETED,
                deleted_at=deleted_at,
                updated_at=updated_at,
            )
        )
        if commit:
            await self._session.commit()
        else:
            await self._session.flush()

    async def set_reaction(
        self,
        *,
        content_id: uuid.UUID,
        user_id: uuid.UUID,
        reaction_type: ReactionTypeEnum,
    ) -> None:
        existing = await self._get_reaction(content_id=content_id, user_id=user_id)
        if existing is None:
            await self._session.execute(
                insert(ContentReactionModel).values(
                    content_id=content_id,
                    user_id=user_id,
                    reaction_type=reaction_type,
                )
            )
            await self._update_reaction_counters(
                content_id=content_id,
                like_delta=1 if reaction_type == ReactionTypeEnum.LIKE else 0,
                dislike_delta=1 if reaction_type == ReactionTypeEnum.DISLIKE else 0,
            )
            await self._session.commit()
            return
        if existing.reaction_type == reaction_type:
            return
        await self._session.execute(
            update(ContentReactionModel)
            .where(ContentReactionModel.content_id == content_id)
            .where(ContentReactionModel.user_id == user_id)
            .values(reaction_type=reaction_type)
        )
        await self._update_reaction_counters(
            content_id=content_id,
            like_delta=1 if reaction_type == ReactionTypeEnum.LIKE else -1,
            dislike_delta=1 if reaction_type == ReactionTypeEnum.DISLIKE else -1,
        )
        await self._session.commit()

    async def remove_reaction(
        self,
        *,
        content_id: uuid.UUID,
        user_id: uuid.UUID,
        reaction_type: ReactionTypeEnum,
    ) -> None:
        existing = await self._get_reaction(content_id=content_id, user_id=user_id)
        if existing is None or existing.reaction_type != reaction_type:
            return
        await self._session.execute(
            delete(ContentReactionModel)
            .where(ContentReactionModel.content_id == content_id)
            .where(ContentReactionModel.user_id == user_id)
        )
        await self._update_reaction_counters(
            content_id=content_id,
            like_delta=-1 if reaction_type == ReactionTypeEnum.LIKE else 0,
            dislike_delta=-1 if reaction_type == ReactionTypeEnum.DISLIKE else 0,
        )
        await self._session.commit()

    async def update_processing_for_source_asset(
        self,
        *,
        asset_id: uuid.UUID,
        processing_status: VideoProcessingStatusEnum,
        duration_seconds: int | None,
        width: int | None,
        height: int | None,
        orientation,
        available_quality_metadata: dict[str, object],
        processing_error: str | None,
        now: datetime.datetime,
    ) -> None:
        result = await self._session.execute(
            select(ContentAssetModel.content_id)
            .where(ContentAssetModel.asset_id == asset_id)
            .where(ContentAssetModel.attachment_type == AttachmentTypeEnum.VIDEO_SOURCE)
            .where(ContentAssetModel.deleted_at.is_(None))
        )
        content_ids = list(result.scalars().all())
        for content_id in content_ids:
            await self.update_playback_details(
                content_id=content_id,
                duration_seconds=duration_seconds,
                width=width,
                height=height,
                orientation=orientation,
                processing_status=processing_status,
                processing_error=processing_error,
                available_quality_metadata=available_quality_metadata,
                updated_at=now,
                commit=False,
            )
            if processing_status == VideoProcessingStatusEnum.READY:
                await self._auto_publish_if_requested(content_id=content_id, now=now)
        await self._session.commit()

    async def commit(self) -> None:
        await self._session.commit()

    async def _auto_publish_if_requested(
        self,
        *,
        content_id: uuid.UUID,
        now: datetime.datetime,
    ) -> None:
        video = await self.get_single(content_id=content_id)
        if video is None or video.video_details.publish_requested_at is None:
            return
        error = await self._publish_validation_error(video)
        if error is not None:
            await self._session.execute(
                update(VideoPlaybackDetailsModel)
                .where(VideoPlaybackDetailsModel.content_id == content_id)
                .values(processing_error=error, updated_at=now)
            )
            return
        await self._session.execute(
            update(ContentModel)
            .where(ContentModel.content_id == content_id)
            .values(
                status=ContentStatusEnum.PUBLISHED,
                published_at=now if video.published_at is None else video.published_at,
                updated_at=now,
            )
        )
        await self._session.execute(
            update(VideoPlaybackDetailsModel)
            .where(VideoPlaybackDetailsModel.content_id == content_id)
            .values(processing_error=None, updated_at=now)
        )

    async def _publish_validation_error(self, video) -> str | None:  # type: ignore[no-untyped-def]
        if not (video.title or "").strip():
            return "Publish validation failed: title is required"
        has_cover = await self._session.scalar(
            select(
                exists().where(
                    ContentAssetModel.content_id == video.content_id,
                    ContentAssetModel.attachment_type == AttachmentTypeEnum.COVER,
                    ContentAssetModel.deleted_at.is_(None),
                )
            )
        )
        if not has_cover:
            return "Publish validation failed: cover asset is required"
        return None

    async def _get_reaction(
        self,
        *,
        content_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> ContentReactionModel | None:
        result = await self._session.execute(
            select(ContentReactionModel)
            .where(ContentReactionModel.content_id == content_id)
            .where(ContentReactionModel.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def _update_reaction_counters(
        self,
        *,
        content_id: uuid.UUID,
        like_delta: int,
        dislike_delta: int,
    ) -> None:
        await self._session.execute(
            update(ContentModel)
            .where(ContentModel.content_id == content_id)
            .values(
                likes_count=ContentModel.likes_count + like_delta,
                dislikes_count=ContentModel.dislikes_count + dislike_delta,
            )
        )

    def _build_video_query(self, viewer_id: uuid.UUID | None):
        reaction_subquery = self._reaction_subquery(viewer_id=viewer_id)
        base_options = (
            selectinload(ContentModel.author).selectinload(UserModel.subscribers),
            selectinload(ContentModel.author)
            .selectinload(UserModel.avatar_asset)
            .selectinload(AssetModel.variants),
            selectinload(ContentModel.video_details),
            selectinload(ContentModel.video_playback_details),
            selectinload(ContentModel.tags),
            selectinload(ContentModel.asset_links)
            .selectinload(ContentAssetModel.asset)
            .selectinload(AssetModel.variants),
        )
        if reaction_subquery is None:
            return (
                select(ContentModel)
                .where(ContentModel.content_type == ContentTypeEnum.VIDEO)
                .options(*base_options)
            )
        return (
            select(ContentModel, reaction_subquery.c.reaction_type.label("my_reaction"))
            .outerjoin(reaction_subquery, ContentModel.content_id == reaction_subquery.c.content_id)
            .where(ContentModel.content_type == ContentTypeEnum.VIDEO)
            .options(*base_options)
        )

    def _reaction_subquery(self, viewer_id: uuid.UUID | None):
        if viewer_id is None:
            return None
        return (
            select(ContentReactionModel.content_id, ContentReactionModel.reaction_type)
            .where(ContentReactionModel.user_id == viewer_id)
            .subquery()
        )

    def _many(self, result, viewer_id: uuid.UUID | None) -> list[ContentModel]:  # type: ignore[no-untyped-def]
        if viewer_id is None:
            videos = list(result.scalars().unique().all())
            for video in videos:
                video.my_reaction = None
                video.is_owner = False
            return videos
        videos: list[ContentModel] = []
        for video, my_reaction in result.unique().all():
            video.my_reaction = my_reaction
            video.is_owner = video.author_id == viewer_id
            videos.append(video)
        return videos

    def _one_or_none(self, result, viewer_id: uuid.UUID | None) -> ContentModel | None:  # type: ignore[no-untyped-def]
        if viewer_id is None:
            video = result.scalar_one_or_none()
            if video is not None:
                video.my_reaction = None
                video.is_owner = False
            return video
        row = result.one_or_none()
        if row is None:
            return None
        video, my_reaction = row
        video.my_reaction = my_reaction
        video.is_owner = video.author_id == viewer_id
        return video

    def _order_by_clause(self, order: VideoOrder, order_desc: bool):
        order_mapping = {
            VideoOrder.ID: ContentModel.content_id,
            VideoOrder.CREATED_AT: ContentModel.created_at,
            VideoOrder.UPDATED_AT: ContentModel.updated_at,
            VideoOrder.PUBLISHED_AT: ContentModel.published_at,
        }
        column = order_mapping[order]
        return desc(column) if order_desc else column
