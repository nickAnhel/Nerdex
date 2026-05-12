from src.chats.models import ChatModel, ChatTimelineItemModel, MembershipModel


def test_membership_read_state_columns_are_registered() -> None:
    columns = MembershipModel.__table__.columns

    assert "last_read_message_id" in columns
    assert columns["last_read_message_id"].nullable is True
    assert "is_muted" in columns
    assert columns["is_muted"].nullable is False


def test_membership_last_read_message_index_is_registered() -> None:
    indexes = {index.name: index for index in MembershipModel.__table__.indexes}

    index = indexes["ix_chat_user_last_read_message_id"]
    assert [column.name for column in index.columns] == ["last_read_message_id"]


def test_chat_timeline_seq_column_is_registered() -> None:
    columns = ChatModel.__table__.columns

    assert "last_timeline_seq" in columns
    assert columns["last_timeline_seq"].nullable is False


def test_chat_timeline_item_constraints_are_registered() -> None:
    constraints = {
        constraint.name: constraint
        for constraint in ChatTimelineItemModel.__table__.constraints
    }

    assert "ck_chat_timeline_items_item_type" in constraints
    assert "ck_chat_timeline_items_single_ref" in constraints
    assert "uq_chat_timeline_items_message_id" in constraints
    assert "uq_chat_timeline_items_event_id" in constraints


def test_chat_timeline_item_chat_seq_index_is_registered() -> None:
    indexes = {index.name: index for index in ChatTimelineItemModel.__table__.indexes}

    index = indexes["ix_chat_timeline_items_chat_seq"]
    assert [column.name for column in index.columns] == ["chat_id", "chat_seq"]
