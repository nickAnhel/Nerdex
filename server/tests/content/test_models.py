from sqlalchemy.dialects import postgresql

from src.content.enums import (
    ContentStatusEnum,
    ContentTypeEnum,
    ContentVisibilityEnum,
    ReactionTypeEnum,
)
from src.content.models import ContentModel, ContentReactionModel


def _bind_value(column_type, value):  # type: ignore[no-untyped-def]
    processor = column_type.bind_processor(postgresql.dialect())
    return processor(value) if processor is not None else value


def _result_value(column_type, value):  # type: ignore[no-untyped-def]
    processor = column_type.result_processor(postgresql.dialect(), None)
    return processor(value) if processor is not None else value


def test_content_enum_columns_bind_lowercase_values() -> None:
    assert _bind_value(ContentModel.__table__.c.content_type.type, ContentTypeEnum.POST) == "post"
    assert _bind_value(ContentModel.__table__.c.status.type, ContentStatusEnum.PUBLISHED) == "published"
    assert _bind_value(ContentModel.__table__.c.visibility.type, ContentVisibilityEnum.PUBLIC) == "public"


def test_content_enum_columns_restore_python_enums_from_db_values() -> None:
    assert _result_value(ContentModel.__table__.c.content_type.type, "post") == ContentTypeEnum.POST
    assert _result_value(ContentModel.__table__.c.status.type, "published") == ContentStatusEnum.PUBLISHED
    assert _result_value(ContentModel.__table__.c.visibility.type, "public") == ContentVisibilityEnum.PUBLIC


def test_reaction_enum_column_bind_and_restore_lowercase_values() -> None:
    column_type = ContentReactionModel.__table__.c.reaction_type.type

    assert _bind_value(column_type, ReactionTypeEnum.LIKE) == "like"
    assert _result_value(column_type, "like") == ReactionTypeEnum.LIKE
