from __future__ import annotations

import datetime
import uuid

from sqlalchemy import delete, desc, exists, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.assets.enums import AttachmentTypeEnum
from src.assets.models import AssetModel, ContentAssetModel
from src.content.enums import ContentStatusEnum, ContentTypeEnum, ContentVisibilityEnum, ReactionTypeEnum
from src.content.models import ContentModel, ContentReactionModel, ContentViewSessionModel
from src.moments.enums import MomentOrder, MomentProfileFilter
from src.moments.models import MomentDetailsModel
from src.users.models import UserModel
from src.videos.enums import VideoOrientationEnum, VideoProcessingStatusEnum
from src.videos.models import VideoPlaybackDetailsModel


MOMENT_ATTACHMENT_TYPES = (
    AttachmentTypeEnum.VIDEO_SOURCE,
    AttachmentTypeEnum.COVER,
)


class MomentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        author_id: uuid.UUID,
        caption: str,
        excerpt: str,
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
                content_type=ContentTypeEnum.MOMENT,
                status=status,
                visibility=visibility,
                title=None,
                excerpt=excerpt,
                created_at=created_at,
                updated_at=updated_at,
                published_at=published_at,
            )
            .returning(ContentModel.content_id)
        )
        content_id = result.scalar_one()
        await self._session.execute(
            insert(MomentDetailsModel).values(
                content_id=content_id,
                caption=caption,
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
        stmt = self._build_moment_query(viewer_id=viewer_id).where(ContentModel.content_id == content_id)
        result = await self._session.execute(stmt)
        return self._one_or_none(result, viewer_id=viewer_id)

    async def get_feed(
        self,
        *,
        viewer_id: uuid.UUID | None,
        offset: int,
        limit: int,
    ) -> list[ContentModel]:
        score = (
            ContentModel.views_count * 2
            + ContentModel.likes_count * 4
            + ContentModel.comments_count * 3
        )
        stmt = (
            self._ready_public_query(viewer_id=viewer_id)
            .order_by(desc(score), desc(ContentModel.published_at), desc(ContentModel.created_at))
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return self._many(result, viewer_id=viewer_id)

    async def get_author_moments(
        self,
        *,
        author_id: uuid.UUID,
        viewer_id: uuid.UUID | None,
        profile_filter: MomentProfileFilter,
        order: MomentOrder,
        order_desc: bool,
        offset: int,
        limit: int,
    ) -> list[ContentModel]:
        stmt = (
            self._build_moment_query(viewer_id=viewer_id)
            .where(ContentModel.author_id == author_id)
            .where(ContentModel.deleted_at.is_(None))
        )
        if viewer_id == author_id:
            if profile_filter == MomentProfileFilter.ALL:
                stmt = stmt.where(ContentModel.status.in_([ContentStatusEnum.PUBLISHED, ContentStatusEnum.DRAFT]))
            elif profile_filter == MomentProfileFilter.DRAFTS:
                stmt = stmt.where(ContentModel.status == ContentStatusEnum.DRAFT)
            elif profile_filter == MomentProfileFilter.PRIVATE:
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

    async def update_moment(
        self,
        *,
        content_id: uuid.UUID,
        caption: str,
        excerpt: str,
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
                excerpt=excerpt,
                status=status,
                visibility=visibility,
                updated_at=updated_at,
                published_at=published_at,
            )
        )
        await self._session.execute(
            update(MomentDetailsModel)
            .where(MomentDetailsModel.content_id == content_id)
            .values(
                caption=caption,
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
                ContentAssetModel.attachment_type.in_(MOMENT_ATTACHMENT_TYPES),
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
                ContentAssetModel.attachment_type.in_(MOMENT_ATTACHMENT_TYPES),
            )
        )
        return set(result.scalars().all())

    async def get_latest_view_session(
        self,
        *,
        content_id: uuid.UUID,
        viewer_id: uuid.UUID,
    ) -> ContentViewSessionModel | None:
        result = await self._session.execute(
            select(ContentViewSessionModel)
            .where(ContentViewSessionModel.content_id == content_id)
            .where(ContentViewSessionModel.viewer_id == viewer_id)
            .order_by(desc(ContentViewSessionModel.last_seen_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def soft_delete_moment(
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
            .join(ContentModel, ContentModel.content_id == ContentAssetModel.content_id)
            .where(ContentAssetModel.asset_id == asset_id)
            .where(ContentAssetModel.attachment_type == AttachmentTypeEnum.VIDEO_SOURCE)
            .where(ContentAssetModel.deleted_at.is_(None))
            .where(ContentModel.content_type == ContentTypeEnum.MOMENT)
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
        moment = await self.get_single(content_id=content_id)
        if moment is None or moment.moment_details.publish_requested_at is None:
            return
        if moment.status == ContentStatusEnum.PUBLISHED or moment.deleted_at is not None:
            return
        error = await self._publish_validation_error(moment)
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
                published_at=now if moment.published_at is None else moment.published_at,
                updated_at=now,
            )
        )
        await self._session.execute(
            update(VideoPlaybackDetailsModel)
            .where(VideoPlaybackDetailsModel.content_id == content_id)
            .values(processing_error=None, updated_at=now)
        )

    async def _publish_validation_error(self, moment) -> str | None:  # type: ignore[no-untyped-def]
        playback = moment.video_playback_details
        if playback is None or playback.processing_status != VideoProcessingStatusEnum.READY:
            return "Publish validation failed: source processing is not ready"
        if playback.orientation != VideoOrientationEnum.PORTRAIT:
            return "Publish validation failed: moment source must be portrait"
        if playback.duration_seconds is None:
            return "Publish validation failed: moment duration is unavailable"
        if playback.duration_seconds > 90:
            return "Publish validation failed: moment source must be 90 seconds or shorter"
        for attachment_type, message in (
            (AttachmentTypeEnum.VIDEO_SOURCE, "source asset is required"),
            (AttachmentTypeEnum.COVER, "cover asset is required"),
        ):
            exists_result = await self._session.scalar(
                select(
                    exists().where(
                        ContentAssetModel.content_id == moment.content_id,
                        ContentAssetModel.attachment_type == attachment_type,
                        ContentAssetModel.deleted_at.is_(None),
                    )
                )
            )
            if not exists_result:
                return f"Publish validation failed: {message}"
        return None

    def _build_moment_query(self, viewer_id: uuid.UUID | None):
        reaction_subquery = self._reaction_subquery(viewer_id=viewer_id)
        base_options = (
            selectinload(ContentModel.author).selectinload(UserModel.subscribers),
            selectinload(ContentModel.author)
            .selectinload(UserModel.avatar_asset)
            .selectinload(AssetModel.variants),
            selectinload(ContentModel.moment_details),
            selectinload(ContentModel.video_playback_details),
            selectinload(ContentModel.tags),
            selectinload(ContentModel.asset_links)
            .selectinload(ContentAssetModel.asset)
            .selectinload(AssetModel.variants),
        )
        if reaction_subquery is None:
            return (
                select(ContentModel)
                .where(ContentModel.content_type == ContentTypeEnum.MOMENT)
                .options(*base_options)
            )
        return (
            select(ContentModel, reaction_subquery.c.reaction_type.label("my_reaction"))
            .outerjoin(reaction_subquery, ContentModel.content_id == reaction_subquery.c.content_id)
            .where(ContentModel.content_type == ContentTypeEnum.MOMENT)
            .options(*base_options)
        )

    def _ready_public_query(self, viewer_id: uuid.UUID | None):
        return (
            self._build_moment_query(viewer_id=viewer_id)
            .join(VideoPlaybackDetailsModel)
            .where(ContentModel.status == ContentStatusEnum.PUBLISHED)
            .where(ContentModel.visibility == ContentVisibilityEnum.PUBLIC)
            .where(ContentModel.deleted_at.is_(None))
            .where(VideoPlaybackDetailsModel.processing_status == VideoProcessingStatusEnum.READY)
        )

    def _reaction_subquery(self, viewer_id: uuid.UUID | None):
        if viewer_id is None:
            return None
        return (
            select(ContentReactionModel.content_id, ContentReactionModel.reaction_type)
            .where(ContentReactionModel.user_id == viewer_id)
            .subquery()
        )

    def _order_by_clause(self, *, order: MomentOrder, order_desc: bool):
        if order == MomentOrder.CREATED_AT:
            column = ContentModel.created_at
        elif order == MomentOrder.UPDATED_AT:
            column = ContentModel.updated_at
        elif order == MomentOrder.PUBLISHED_AT:
            column = ContentModel.published_at
        else:
            column = ContentModel.content_id
        return desc(column) if order_desc else column

    def _many(self, result, viewer_id: uuid.UUID | None) -> list[ContentModel]:  # type: ignore[no-untyped-def]
        if viewer_id is None:
            moments = list(result.scalars().unique().all())
            for moment in moments:
                moment.my_reaction = None
                moment.is_owner = False
            return moments
        moments: list[ContentModel] = []
        for moment, my_reaction in result.unique().all():
            moment.my_reaction = my_reaction
            moment.is_owner = moment.author_id == viewer_id
            moments.append(moment)
        return moments

    def _one_or_none(self, result, viewer_id: uuid.UUID | None) -> ContentModel | None:  # type: ignore[no-untyped-def]
        if viewer_id is None:
            moment = result.scalar_one_or_none()
            if moment is not None:
                moment.my_reaction = None
                moment.is_owner = False
            return moment
        row = result.one_or_none()
        if row is None:
            return None
        moment, my_reaction = row
        moment.my_reaction = my_reaction
        moment.is_owner = moment.author_id == viewer_id
        return moment
