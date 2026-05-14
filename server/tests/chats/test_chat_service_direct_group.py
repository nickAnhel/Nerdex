import uuid
import datetime
from types import SimpleNamespace

import pytest

from src.chats.enums import ChatMemberRole, ChatType
from src.chats.exceptions import CantAddMembers, InvalidChatHistoryCursor
from src.chats.schemas import ChatCreate
from src.chats.service import ChatService
from src.common.model_registry import import_all_models
from src.events.models import EventModel
from src.messages.models import MessageModel
from src.users.models import UserModel

import_all_models()


def _user(user_id: uuid.UUID, username: str):
    return SimpleNamespace(
        user_id=user_id,
        username=username,
        display_name=None,
        bio=None,
        links=[],
        avatar_asset_id=None,
        avatar_crop=None,
        subscribers_count=0,
        is_admin=False,
    )


def _chat(
    *,
    chat_id: uuid.UUID,
    owner_id: uuid.UUID,
    chat_type: str,
    title: str = "Chat",
    is_private: bool = False,
    members=None,
    direct_key: str | None = None,
):
    return SimpleNamespace(
        chat_id=chat_id,
        title=title,
        is_private=is_private,
        chat_type=chat_type,
        owner_id=owner_id,
        direct_key=direct_key,
        members=members or [],
    )


class FakeChatRepository:
    def __init__(self, *, existing_direct=None) -> None:
        self.existing_direct = existing_direct
        self.created_data = None
        self.created_member_roles = None
        self.created_chat_id = uuid.uuid4()
        self.dialogs = []
        self.marked_read = None
        self.history_items = []
        self.history_args = None

    async def get_by_direct_key(self, direct_key: str):
        if self.existing_direct and self.existing_direct.direct_key == direct_key:
            return self.existing_direct
        return None

    async def create_with_member_roles(self, *, data, member_roles):
        self.created_data = data
        self.created_member_roles = member_roles
        return _chat(
            chat_id=self.created_chat_id,
            owner_id=data["owner_id"],
            title=data["title"],
            is_private=data["is_private"],
            chat_type=data["chat_type"],
            direct_key=data.get("direct_key"),
        )

    async def get_single(self, **filters):
        owner_id = self.created_data["owner_id"]
        members = [
            _user(user_id, f"user-{index}")
            for index, (user_id, _role) in enumerate(self.created_member_roles or [])
        ]
        return _chat(
            chat_id=filters["chat_id"],
            owner_id=owner_id,
            title=self.created_data["title"],
            is_private=self.created_data["is_private"],
            chat_type=self.created_data["chat_type"],
            direct_key=self.created_data.get("direct_key"),
            members=members,
        )

    async def get_user_dialogs(self, *, user_id, offset, limit):
        return self.dialogs[offset:offset + limit]

    async def is_member(self, *, chat_id, user_id):
        return True

    async def mark_read(self, *, chat_id, user_id):
        self.marked_read = (chat_id, user_id)
        return uuid.uuid4()

    async def history(self, *, chat_id, limit, before_seq=None, after_seq=None):
        self.history_args = {
            "chat_id": chat_id,
            "limit": limit,
            "before_seq": before_seq,
            "after_seq": after_seq,
        }
        return self.history_items


@pytest.mark.asyncio
async def test_create_direct_chat_adds_owner_and_member_roles() -> None:
    owner_id = uuid.uuid4()
    member_id = uuid.uuid4()
    repository = FakeChatRepository()
    service = ChatService(repository)  # type: ignore[arg-type]

    chat = await service.create_chat(
        user_id=owner_id,
        data=ChatCreate(chat_type=ChatType.DIRECT, member_id=member_id),
    )

    assert chat.chat_type == ChatType.DIRECT
    assert chat.is_private is True
    assert chat.chat_id == repository.created_chat_id
    assert repository.created_member_roles == [
        (owner_id, ChatMemberRole.OWNER),
        (member_id, ChatMemberRole.MEMBER),
    ]
    assert repository.created_data["direct_key"] == ":".join(
        sorted([str(owner_id), str(member_id)])
    )


@pytest.mark.asyncio
async def test_create_direct_chat_returns_existing_direct_chat() -> None:
    owner_id = uuid.uuid4()
    member_id = uuid.uuid4()
    direct_key = ":".join(sorted([str(owner_id), str(member_id)]))
    existing_chat = _chat(
        chat_id=uuid.uuid4(),
        owner_id=owner_id,
        chat_type=ChatType.DIRECT.value,
        title="Direct chat",
        is_private=True,
        direct_key=direct_key,
        members=[
            _user(owner_id, "owner"),
            _user(member_id, "member"),
        ],
    )
    repository = FakeChatRepository(existing_direct=existing_chat)
    service = ChatService(repository)  # type: ignore[arg-type]

    chat = await service.create_chat(
        user_id=owner_id,
        data=ChatCreate(chat_type=ChatType.DIRECT, member_id=member_id),
    )

    assert chat.chat_id == existing_chat.chat_id
    assert repository.created_data is None


@pytest.mark.asyncio
async def test_create_direct_chat_rejects_self_chat() -> None:
    owner_id = uuid.uuid4()
    service = ChatService(FakeChatRepository())  # type: ignore[arg-type]

    with pytest.raises(CantAddMembers):
        await service.create_chat(
            user_id=owner_id,
            data=ChatCreate(chat_type=ChatType.DIRECT, member_id=owner_id),
        )


@pytest.mark.asyncio
async def test_create_group_chat_assigns_owner_and_member_roles() -> None:
    owner_id = uuid.uuid4()
    member_id = uuid.uuid4()
    repository = FakeChatRepository()
    service = ChatService(repository)  # type: ignore[arg-type]

    chat = await service.create_chat(
        user_id=owner_id,
        data=ChatCreate(
            chat_type=ChatType.GROUP,
            title="Study group",
            is_private=True,
            members=[member_id],
        ),
    )

    assert chat.chat_type == ChatType.GROUP
    assert repository.created_data == {
        "title": "Study group",
        "is_private": True,
        "chat_type": ChatType.GROUP.value,
        "owner_id": owner_id,
    }
    assert repository.created_member_roles == [
        (owner_id, ChatMemberRole.OWNER),
        (member_id, ChatMemberRole.MEMBER),
    ]


@pytest.mark.asyncio
async def test_user_dialogs_resolve_direct_display_title_and_unread_state() -> None:
    owner_id = uuid.uuid4()
    member_id = uuid.uuid4()
    read_message_id = uuid.uuid4()
    repository = FakeChatRepository()
    repository.dialogs = [
        _chat(
            chat_id=uuid.uuid4(),
            owner_id=owner_id,
            chat_type=ChatType.DIRECT.value,
            title="Direct chat",
            is_private=True,
            members=[
                _user(owner_id, "owner"),
                _user(member_id, "member"),
            ],
        )
    ]
    setattr(
        repository.dialogs[0],
        "membership",
        SimpleNamespace(
            is_muted=True,
            last_read_message_id=read_message_id,
        ),
    )
    setattr(repository.dialogs[0], "unread_count", 3)
    service = ChatService(repository)  # type: ignore[arg-type]

    dialogs = await service.get_user_joined_chats(
        user=_user(owner_id, "owner"),
        order=None,  # type: ignore[arg-type]
        order_desc=True,
        offset=0,
        limit=10,
    )

    assert dialogs[0].display_title == "member"
    assert dialogs[0].display_avatar is None
    assert dialogs[0].unread_count == 3
    assert dialogs[0].is_muted is True
    assert dialogs[0].last_read_message_id == read_message_id


@pytest.mark.asyncio
async def test_user_dialogs_keep_group_display_title() -> None:
    owner_id = uuid.uuid4()
    repository = FakeChatRepository()
    repository.dialogs = [
        _chat(
            chat_id=uuid.uuid4(),
            owner_id=owner_id,
            chat_type=ChatType.GROUP.value,
            title="Study group",
            members=[_user(owner_id, "owner")],
        )
    ]
    setattr(repository.dialogs[0], "membership", SimpleNamespace())
    service = ChatService(repository)  # type: ignore[arg-type]

    dialogs = await service.get_user_joined_chats(
        user=_user(owner_id, "owner"),
        order=None,  # type: ignore[arg-type]
        order_desc=True,
        offset=0,
        limit=10,
    )

    assert dialogs[0].display_title == "Study group"
    assert dialogs[0].display_avatar is None


@pytest.mark.asyncio
async def test_mark_chat_read_updates_current_member() -> None:
    user_id = uuid.uuid4()
    chat_id = uuid.uuid4()
    repository = FakeChatRepository()
    service = ChatService(repository)  # type: ignore[arg-type]

    await service.mark_chat_read(chat_id=chat_id, user_id=user_id)

    assert repository.marked_read == (chat_id, user_id)


@pytest.mark.asyncio
async def test_chat_history_rejects_conflicting_cursors() -> None:
    service = ChatService(FakeChatRepository())  # type: ignore[arg-type]

    with pytest.raises(InvalidChatHistoryCursor):
        await service.get_chat_history(
            chat_id=uuid.uuid4(),
            limit=10,
            before_seq=2,
            after_seq=1,
        )


@pytest.mark.asyncio
async def test_chat_history_preserves_timeline_order_and_seq() -> None:
    chat_id = uuid.uuid4()
    author = UserModel(
        user_id=uuid.uuid4(),
        username="alice",
        hashed_password="hashed",
        is_admin=False,
        subscribers_count=0,
    )
    message = MessageModel(
        message_id=uuid.uuid4(),
        chat_id=chat_id,
        client_message_id=uuid.uuid4(),
        content="hello",
        user_id=author.user_id,
        created_at=datetime.datetime.now(datetime.timezone.utc),
    )
    message.user = author
    event = EventModel(
        event_id=uuid.uuid4(),
        chat_id=chat_id,
        event_type="joined",
        user_id=author.user_id,
        created_at=datetime.datetime.now(datetime.timezone.utc),
    )
    event.user = author
    event.altered_user = None
    setattr(message, "chat_seq", 1)
    setattr(event, "chat_seq", 2)

    repository = FakeChatRepository()
    repository.history_items = [
        (SimpleNamespace(chat_seq=1), message),
        (SimpleNamespace(chat_seq=2), event),
    ]
    service = ChatService(repository)  # type: ignore[arg-type]

    history = await service.get_chat_history(chat_id=chat_id, limit=10)

    assert [item.item_type for item in history] == ["message", "event"]
    assert [item.chat_seq for item in history] == [1, 2]
    assert history[1].user.display_name == "alice"


@pytest.mark.asyncio
async def test_chat_history_passes_cursor_to_repository() -> None:
    chat_id = uuid.uuid4()
    repository = FakeChatRepository()
    service = ChatService(repository)  # type: ignore[arg-type]

    await service.get_chat_history(chat_id=chat_id, limit=5, after_seq=42)

    assert repository.history_args == {
        "chat_id": chat_id,
        "limit": 5,
        "before_seq": None,
        "after_seq": 42,
    }
