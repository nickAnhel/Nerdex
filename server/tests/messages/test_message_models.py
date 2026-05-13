from src.messages.models import MessageModel, MessageSharedContentModel


def test_message_client_message_id_idempotency_constraint_is_registered() -> None:
    constraints = {
        constraint.name: constraint
        for constraint in MessageModel.__table__.constraints
    }

    constraint = constraints["uq_messages_chat_user_client_message_id"]
    assert [column.name for column in constraint.columns] == [
        "chat_id",
        "user_id",
        "client_message_id",
    ]


def test_message_chat_created_at_index_is_registered() -> None:
    indexes = {index.name: index for index in MessageModel.__table__.indexes}

    index = indexes["ix_messages_chat_created_at"]
    assert [column.name for column in index.columns] == ["chat_id", "created_at"]


def test_message_edit_delete_columns_are_registered() -> None:
    columns = MessageModel.__table__.columns

    assert "edited_at" in columns
    assert "deleted_at" in columns
    assert "deleted_by" in columns


def test_message_reply_to_message_column_and_index_are_registered() -> None:
    columns = MessageModel.__table__.columns
    indexes = {index.name: index for index in MessageModel.__table__.indexes}

    assert "reply_to_message_id" in columns
    index = indexes["ix_messages_chat_reply_to_message_id"]
    assert [column.name for column in index.columns] == [
        "chat_id",
        "reply_to_message_id",
    ]


def test_message_shared_content_table_is_registered() -> None:
    columns = MessageSharedContentModel.__table__.columns
    indexes = {index.name: index for index in MessageSharedContentModel.__table__.indexes}

    assert "message_id" in columns
    assert "content_id" in columns
    assert [column.name for column in indexes["ix_message_shared_content_content_id"].columns] == [
        "content_id",
    ]
