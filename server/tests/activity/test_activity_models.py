from sqlalchemy.dialects import postgresql

from src.activity.enums import ActivityActionTypeEnum
from src.activity.models import ActivityEventModel


def _bind_value(column_type, value):  # type: ignore[no-untyped-def]
    processor = column_type.bind_processor(postgresql.dialect())
    return processor(value) if processor is not None else value


def _result_value(column_type, value):  # type: ignore[no-untyped-def]
    processor = column_type.result_processor(postgresql.dialect(), None)
    return processor(value) if processor is not None else value


def test_activity_action_enum_binds_lowercase_values() -> None:
    column_type = ActivityEventModel.__table__.c.action_type.type

    assert _bind_value(column_type, ActivityActionTypeEnum.CONTENT_VIEW) == "content_view"
    assert _result_value(column_type, "content_view") == ActivityActionTypeEnum.CONTENT_VIEW


def test_activity_event_table_shape() -> None:
    table = ActivityEventModel.__table__

    assert table.name == "user_activity_events"
    assert table.c.content_id.nullable is True
    assert table.c.target_user_id.nullable is True
    assert table.c.comment_id.nullable is True
    assert table.c.metadata.nullable is False
    assert {index.name for index in table.indexes} >= {
        "ix_user_activity_events_user_created_at",
        "ix_user_activity_events_user_action_created_at",
        "ix_user_activity_events_user_content_type_created_at",
        "ix_user_activity_events_content_created_at",
        "ix_user_activity_events_target_user_created_at",
    }
