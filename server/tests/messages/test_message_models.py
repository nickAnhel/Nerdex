from src.messages.models import MessageModel


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
