from __future__ import annotations

import uuid

from src.content.enums import ContentTypeEnum
from src.content.projectors import ContentProjectorRegistry
from src.search.enums import SearchSortEnum, SearchTypeEnum
from src.search.repository import SearchRepository
from src.search.schemas import SearchListGet, SearchResultItemGet
from src.users.presentation import build_user_get


class SearchService:
    def __init__(
        self,
        repository: SearchRepository,
        projector_registry: ContentProjectorRegistry,
        asset_storage,
    ) -> None:
        self._repository = repository
        self._projector_registry = projector_registry
        self._asset_storage = asset_storage

    async def search(
        self,
        *,
        query: str,
        search_type: SearchTypeEnum,
        sort: SearchSortEnum,
        offset: int,
        limit: int,
        viewer_id: uuid.UUID | None,
    ) -> SearchListGet:
        normalized_query = " ".join(query.split())
        if not normalized_query:
            return SearchListGet(items=[], offset=offset, limit=limit, has_more=False)

        if search_type == SearchTypeEnum.AUTHOR:
            author_matches, has_more = await self._repository.search_authors(
                query_text=normalized_query,
                sort=sort,
                offset=offset,
                limit=limit,
            )
            authors = await self._repository.get_users_by_ids(
                user_ids=[match.author_id for match in author_matches],
            )
            items = []
            for match in author_matches:
                author = authors.get(match.author_id)
                if author is None:
                    continue
                items.append(
                    SearchResultItemGet(
                        result_type="author",
                        content=None,
                        author=await build_user_get(
                            author,
                            viewer_id=viewer_id,
                            storage=self._asset_storage,
                        ),
                        score=match.score,
                    )
                )
            return SearchListGet(items=items, offset=offset, limit=limit, has_more=has_more)

        if search_type == SearchTypeEnum.ALL:
            mixed_matches, has_more = await self._repository.search_all(
                query_text=normalized_query,
                sort=sort,
                offset=offset,
                limit=limit,
            )
            content_ids = [match.content_id for match in mixed_matches if match.content_id is not None]
            author_ids = [match.author_id for match in mixed_matches if match.author_id is not None]
            content_map = await self._repository.get_content_by_ids(
                content_ids=content_ids,
                viewer_id=viewer_id,
            )
            author_map = await self._repository.get_users_by_ids(user_ids=author_ids)
            items = []
            for match in mixed_matches:
                if match.result_type == "content" and match.content_id is not None:
                    content = content_map.get(match.content_id)
                    if content is None:
                        continue
                    projector = self._projector_registry.get(content.content_type)
                    items.append(
                        SearchResultItemGet(
                            result_type="content",
                            content=await projector.project_feed_item(
                                content,
                                viewer_id=viewer_id,
                                storage=self._asset_storage,
                            ),
                            author=None,
                            score=match.score,
                        )
                    )
                elif match.result_type == "author" and match.author_id is not None:
                    author = author_map.get(match.author_id)
                    if author is None:
                        continue
                    items.append(
                        SearchResultItemGet(
                            result_type="author",
                            content=None,
                            author=await build_user_get(
                                author,
                                viewer_id=viewer_id,
                                storage=self._asset_storage,
                            ),
                            score=match.score,
                        )
                    )
            return SearchListGet(items=items, offset=offset, limit=limit, has_more=has_more)

        content_type = self._content_type_from_search_type(search_type)
        content_matches, has_more = await self._repository.search_content(
            query_text=normalized_query,
            content_type=content_type,
            sort=sort,
            offset=offset,
            limit=limit,
        )
        content_map = await self._repository.get_content_by_ids(
            content_ids=[match.content_id for match in content_matches],
            viewer_id=viewer_id,
        )

        items = []
        for match in content_matches:
            content = content_map.get(match.content_id)
            if content is None:
                continue
            projector = self._projector_registry.get(content.content_type)
            items.append(
                SearchResultItemGet(
                    result_type="content",
                    content=await projector.project_feed_item(
                        content,
                        viewer_id=viewer_id,
                        storage=self._asset_storage,
                    ),
                    author=None,
                    score=match.score,
                )
            )

        return SearchListGet(items=items, offset=offset, limit=limit, has_more=has_more)

    def _content_type_from_search_type(self, search_type: SearchTypeEnum) -> ContentTypeEnum:
        mapping = {
            SearchTypeEnum.POST: ContentTypeEnum.POST,
            SearchTypeEnum.ARTICLE: ContentTypeEnum.ARTICLE,
            SearchTypeEnum.VIDEO: ContentTypeEnum.VIDEO,
            SearchTypeEnum.MOMENT: ContentTypeEnum.MOMENT,
        }
        content_type = mapping.get(search_type)
        if content_type is None:
            raise ValueError(f"Unsupported search type: {search_type}")
        return content_type
