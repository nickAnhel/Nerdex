from src.chats.models import MembershipModel


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
