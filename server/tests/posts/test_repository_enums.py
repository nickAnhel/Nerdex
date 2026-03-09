import uuid
from enum import Enum

from sqlalchemy.dialects import postgresql
from sqlalchemy import select
from sqlalchemy.sql.elements import BindParameter
from sqlalchemy.sql.visitors import iterate

import src.chats.models  # noqa: F401
import src.events.models  # noqa: F401
import src.messages.models  # noqa: F401
from src.content.enums import ContentStatusEnum, ContentTypeEnum, ContentVisibilityEnum
from src.content.models import ContentModel
from src.posts.enums import PostOrder
from src.posts.repository import PostRepository
from src.users.models import SubscriptionModel


def _enum_bind_values(stmt) -> set[str]:  # type: ignore[no-untyped-def]
    values: set[str] = set()
    dialect = postgresql.dialect()

    for element in iterate(stmt):
        if not isinstance(element, BindParameter):
            continue
        if not isinstance(element.value, Enum):
            continue

        processor = element.type.bind_processor(dialect)
        value = processor(element.value) if processor is not None else element.value
        values.add(value)

    return values


def test_feed_query_binds_lowercase_content_enums() -> None:
    repository = PostRepository(session=None)  # type: ignore[arg-type]

    stmt = (
        repository._build_post_query(viewer_id=None)
        .where(ContentModel.status == ContentStatusEnum.PUBLISHED)
        .where(ContentModel.visibility == ContentVisibilityEnum.PUBLIC)
        .where(ContentModel.deleted_at.is_(None))
        .order_by(repository._order_by_clause(order=PostOrder.CREATED_AT, order_desc=True))
        .offset(0)
        .limit(5)
    )

    assert _enum_bind_values(stmt) == {"post", "published", "public"}


def test_subscriptions_query_binds_lowercase_content_enums() -> None:
    repository = PostRepository(session=None)  # type: ignore[arg-type]
    user_id = uuid.uuid4()

    subs_subquery = (
        select(SubscriptionModel.subscribed_id)
        .where(SubscriptionModel.subscriber_id == user_id)
        .subquery()
    )

    stmt = (
        repository._build_post_query(viewer_id=user_id)
        .where(ContentModel.author_id.in_(select(subs_subquery.c.subscribed_id)))
        .where(ContentModel.status == ContentStatusEnum.PUBLISHED)
        .where(ContentModel.visibility == ContentVisibilityEnum.PUBLIC)
        .where(ContentModel.deleted_at.is_(None))
        .order_by(repository._order_by_clause(order=PostOrder.CREATED_AT, order_desc=True))
        .offset(0)
        .limit(5)
    )

    enum_values = _enum_bind_values(stmt)

    assert "post" in enum_values
    assert "published" in enum_values
    assert "public" in enum_values
