from __future__ import annotations

import uuid

from src.assets.storage import AssetStorage
from src.content.enums_list import ContentOrder
from src.content.projectors import ContentProjectorRegistry
from src.content.repository import ContentRepository
from src.content.schemas import ContentListItemGet


class ContentService:
    def __init__(
        self,
        repository: ContentRepository,
        asset_storage: AssetStorage,
        projector_registry: ContentProjectorRegistry,
    ) -> None:
        self._repository = repository
        self._asset_storage = asset_storage
        self._projector_registry = projector_registry

    async def get_feed(
        self,
        *,
        order: ContentOrder,
        desc: bool,
        offset: int,
        limit: int,
        viewer_id: uuid.UUID | None,
    ) -> list[ContentListItemGet]:
        content_items = await self._repository.get_feed(
            viewer_id=viewer_id,
            order=order,
            order_desc=desc,
            offset=offset,
            limit=limit,
        )
        return [await self._build_feed_item(item, viewer_id=viewer_id) for item in content_items]

    async def get_subscriptions_feed(
        self,
        *,
        user_id: uuid.UUID,
        order: ContentOrder,
        desc: bool,
        offset: int,
        limit: int,
    ) -> list[ContentListItemGet]:
        content_items = await self._repository.get_user_subscriptions_feed(
            user_id=user_id,
            order=order,
            order_desc=desc,
            offset=offset,
            limit=limit,
        )
        return [await self._build_feed_item(item, viewer_id=user_id) for item in content_items]

    async def _build_feed_item(
        self,
        item,
        *,
        viewer_id: uuid.UUID | None,
    ) -> ContentListItemGet:
        projector = self._projector_registry.get(item.content_type)
        return await projector.project_feed_item(
            item,
            viewer_id=viewer_id,
            storage=self._asset_storage,
        )
