import datetime
import asyncio
import uuid

import pytest
from sqlalchemy.exc import NoResultFound

from src.common.exceptions import PermissionDenied
from src.assets.enums import AssetStatusEnum, AssetVariantStatusEnum, AssetVariantTypeEnum
from src.content.enums import ContentStatusEnum, ContentTypeEnum, ContentVisibilityEnum, ReactionTypeEnum
from src.content.schemas import ContentListItemGet
from src.messages.exceptions import (
    CantDeleteMessage,
    CantReactToMessage,
    CantUpdateMessage,
    InvalidMessageAssets,
    InvalidMessageReply,
)
from src.messages.schemas import (
    MessageCreate,
    MessageUpdate,
    SharedContentMessagesCreate,
)
from src.messages.service import DELETED_MESSAGE_STUB, MessageService
from src.users.schemas import UserGet


class _User:
    user_id = uuid.uuid4()
    avatar_asset_id = None
    avatar = None
    avatar_crop = None
    username = "alice"
    subscribers_count = 0
    is_admin = False
    subscribers = []


class _Message:
    def __init__(
        self,
        *,
        chat_id=None,
        deleted_at=None,
        reply_to_message=None,
        shared_content=None,
        reactions=None,
    ) -> None:
        self.message_id = uuid.uuid4()
        self.chat_id = chat_id or uuid.uuid4()
        self.client_message_id = uuid.uuid4()
        self.content = "hello"
        self.user_id = _User.user_id
        self.created_at = datetime.datetime.now(datetime.timezone.utc)
        self.edited_at = None
        self.deleted_at = deleted_at
        self.deleted_by = _User.user_id if deleted_at is not None else None
        self.chat_seq = 1
        self.user = _User()
        self.reply_to_message_id = (
            reply_to_message.message_id if reply_to_message is not None else None
        )
        self.reply_to_message = reply_to_message
        self.asset_links = []
        self.shared_content = shared_content
        self.reactions = reactions or []

    @property
    def content_ellipsis(self) -> str:
        return self.content


class _Reaction:
    def __init__(self, *, user_id, reaction_type) -> None:
        self.user_id = user_id
        self.reaction_type = reaction_type


class _Repository:
    def __init__(self, message=None, *, raises=None) -> None:
        self.message = message
        self.raises = raises
        self.created_asset_ids = None
        self.created_messages = []
        self.reaction_calls = []
        self.search_calls = []

    async def update(self, **_kwargs):
        if self.raises is not None:
            raise self.raises
        return self.message

    async def soft_delete(self, **_kwargs):
        if self.raises is not None:
            raise self.raises
        return self.message

    async def create(self, **kwargs):
        if self.raises is not None:
            raise self.raises
        self.created_asset_ids = kwargs.get("asset_ids")
        self.created_messages.append((kwargs.get("data"), kwargs.get("shared_content_id")))
        return self.message

    async def create_idempotent(self, **kwargs):
        if self.raises is not None:
            raise self.raises
        self.created_asset_ids = kwargs.get("asset_ids")
        return self.message

    async def get_reply_target(self, **_kwargs):
        if self.raises is not None:
            raise self.raises
        return self.message.reply_to_message

    async def get_single(self, **_kwargs):
        if self.raises is not None:
            raise self.raises
        return self.message

    async def search(self, **kwargs):
        if self.raises is not None:
            raise self.raises
        self.search_calls.append(kwargs)
        return [self.message], 3

    async def set_reaction(self, **kwargs):
        if self.raises is not None:
            raise self.raises
        self.reaction_calls.append(("set", kwargs))
        existing = next(
            (
                reaction
                for reaction in self.message.reactions
                if reaction.user_id == kwargs["user_id"]
            ),
            None,
        )
        if existing is None:
            self.message.reactions.append(
                _Reaction(
                    user_id=kwargs["user_id"],
                    reaction_type=kwargs["reaction_type"],
                )
            )
        else:
            existing.reaction_type = kwargs["reaction_type"]
        return self.message

    async def remove_reaction(self, **kwargs):
        if self.raises is not None:
            raise self.raises
        self.reaction_calls.append(("remove", kwargs))
        self.message.reactions = [
            reaction
            for reaction in self.message.reactions
            if not (
                reaction.user_id == kwargs["user_id"]
                and reaction.reaction_type == kwargs["reaction_type"]
            )
        ]
        return self.message


class _Variant:
    def __init__(self, *, status=AssetVariantStatusEnum.READY) -> None:
        self.asset_variant_type = AssetVariantTypeEnum.ORIGINAL
        self.status = status


class _Asset:
    def __init__(
        self,
        *,
        asset_id,
        owner_id,
        status=AssetStatusEnum.READY,
        variant_status=AssetVariantStatusEnum.READY,
    ) -> None:
        self.asset_id = asset_id
        self.owner_id = owner_id
        self.status = status
        self.variants = [_Variant(status=variant_status)]


class _AssetRepository:
    def __init__(self, assets) -> None:
        self.assets = assets

    async def get_assets(self, *, asset_ids, owner_id=None):
        return [
            asset
            for asset_id in asset_ids
            if (asset := self.assets.get(asset_id)) is not None
            and (owner_id is None or asset.owner_id == owner_id)
        ]


class _ChatRepository:
    def __init__(self, member_chat_ids) -> None:
        self.member_chat_ids = set(member_chat_ids)

    async def is_member(self, *, chat_id, user_id):
        return chat_id in self.member_chat_ids


class _SharedContent:
    def __init__(self, content_id) -> None:
        self.content_id = content_id
        self.content = type(
            "Content",
            (),
            {
                "content_id": content_id,
            },
        )()


class _SharedContentWithoutLoadedContent:
    def __init__(self, content_id) -> None:
        self.content_id = content_id

    @property
    def content(self):
        raise AssertionError("Shared content preview must not lazy-load content relationship")


class _ContentService:
    def __init__(self, result=None) -> None:
        self.checked = []
        self.result = result

    async def get_shareable_content(self, *, content_id, viewer_id):
        self.checked.append((content_id, viewer_id))
        if self.result is not None:
            return self.result
        return make_content_item(content_id=content_id, my_reaction=None)


def make_content_item(
    *,
    content_id,
    my_reaction: ReactionTypeEnum | None,
) -> ContentListItemGet:
    return ContentListItemGet(
        content_id=content_id,
        content_type=ContentTypeEnum.POST,
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=datetime.datetime.now(datetime.timezone.utc),
        updated_at=datetime.datetime.now(datetime.timezone.utc),
        published_at=datetime.datetime.now(datetime.timezone.utc),
        comments_count=0,
        likes_count=0,
        dislikes_count=0,
        views_count=0,
        user=UserGet(
            user_id=_User.user_id,
            username=_User.username,
            is_admin=False,
            subscribers_count=0,
            avatar=None,
            avatar_asset_id=None,
            is_subscribed=False,
        ),
        tags=[],
        my_reaction=my_reaction,
        is_owner=False,
        post_content="shared post",
    )


@pytest.mark.asyncio
async def test_update_message_returns_author_message() -> None:
    message = _Message()
    service = MessageService(_Repository(message))  # type: ignore[arg-type]

    result = await service.update_message(
        data=MessageUpdate(content="updated"),
        message_id=message.message_id,
        user_id=message.user_id,
    )

    assert result.message_id == message.message_id
    assert result.content == "hello"


@pytest.mark.asyncio
async def test_update_message_rejects_missing_or_deleted_message() -> None:
    service = MessageService(_Repository(raises=NoResultFound()))  # type: ignore[arg-type]

    with pytest.raises(CantUpdateMessage):
        await service.update_message(
            data=MessageUpdate(content="updated"),
            message_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
        )


@pytest.mark.asyncio
async def test_delete_message_returns_deleted_stub() -> None:
    deleted_at = datetime.datetime.now(datetime.timezone.utc)
    message = _Message(deleted_at=deleted_at)
    service = MessageService(_Repository(message))  # type: ignore[arg-type]

    result = await service.delete_message(
        message_id=message.message_id,
        user_id=message.user_id,
    )

    assert result.deleted_at == deleted_at
    assert result.deleted_by == message.user_id
    assert result.content == DELETED_MESSAGE_STUB


@pytest.mark.asyncio
async def test_delete_message_rejects_missing_or_already_deleted_message() -> None:
    service = MessageService(_Repository(raises=NoResultFound()))  # type: ignore[arg-type]

    with pytest.raises(CantDeleteMessage):
        await service.delete_message(
            message_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
        )


@pytest.mark.asyncio
async def test_set_message_reaction_returns_aggregated_reactions() -> None:
    chat_id = uuid.uuid4()
    user_id = uuid.uuid4()
    message = _Message(
        chat_id=chat_id,
        reactions=[
            _Reaction(user_id=uuid.uuid4(), reaction_type=ReactionTypeEnum.LIKE),
        ],
    )
    repository = _Repository(message)
    service = MessageService(
        repository,  # type: ignore[arg-type]
        chat_repository=_ChatRepository([chat_id]),  # type: ignore[arg-type]
    )

    result, previous_reaction_type = await service.set_message_reaction(
        message_id=message.message_id,
        user_id=user_id,
        reaction_type=ReactionTypeEnum.DISLIKE,
    )

    assert previous_reaction_type is None
    assert repository.reaction_calls[0][0] == "set"
    assert result.reactions[0].reaction_type == ReactionTypeEnum.LIKE
    assert result.reactions[0].count == 1
    assert result.reactions[0].reacted_by_me is False
    assert result.reactions[1].reaction_type == ReactionTypeEnum.DISLIKE
    assert result.reactions[1].count == 1
    assert result.reactions[1].reacted_by_me is True


@pytest.mark.asyncio
async def test_remove_message_reaction_clears_reaction_state() -> None:
    chat_id = uuid.uuid4()
    user_id = uuid.uuid4()
    message = _Message(
        chat_id=chat_id,
        reactions=[
            _Reaction(user_id=user_id, reaction_type=ReactionTypeEnum.LIKE),
        ],
    )
    repository = _Repository(message)
    service = MessageService(
        repository,  # type: ignore[arg-type]
        chat_repository=_ChatRepository([chat_id]),  # type: ignore[arg-type]
    )

    result, previous_reaction_type = await service.remove_message_reaction(
        message_id=message.message_id,
        user_id=user_id,
        reaction_type=ReactionTypeEnum.LIKE,
    )

    assert previous_reaction_type == ReactionTypeEnum.LIKE
    assert repository.reaction_calls[0][0] == "remove"
    assert result.reactions[0].count == 0
    assert result.reactions[0].reacted_by_me is False
    assert result.reactions[1].count == 0
    assert result.reactions[1].reacted_by_me is False


@pytest.mark.asyncio
async def test_set_message_reaction_rejects_deleted_message() -> None:
    chat_id = uuid.uuid4()
    message = _Message(
        chat_id=chat_id,
        deleted_at=datetime.datetime.now(datetime.timezone.utc),
    )
    service = MessageService(
        _Repository(message),  # type: ignore[arg-type]
        chat_repository=_ChatRepository([chat_id]),  # type: ignore[arg-type]
    )

    with pytest.raises(CantReactToMessage):
        await service.set_message_reaction(
            message_id=message.message_id,
            user_id=message.user_id,
            reaction_type=ReactionTypeEnum.LIKE,
        )


@pytest.mark.asyncio
async def test_set_message_reaction_rejects_non_member_user() -> None:
    chat_id = uuid.uuid4()
    message = _Message(chat_id=chat_id)
    service = MessageService(
        _Repository(message),  # type: ignore[arg-type]
        chat_repository=_ChatRepository([]),  # type: ignore[arg-type]
    )

    with pytest.raises(PermissionDenied):
        await service.set_message_reaction(
            message_id=message.message_id,
            user_id=uuid.uuid4(),
            reaction_type=ReactionTypeEnum.LIKE,
        )


@pytest.mark.asyncio
async def test_create_message_accepts_reply_in_same_chat() -> None:
    chat_id = uuid.uuid4()
    reply_target = _Message(chat_id=chat_id)
    message = _Message(chat_id=chat_id, reply_to_message=reply_target)
    service = MessageService(_Repository(message))  # type: ignore[arg-type]

    result = await service.create_message(
        MessageCreate(
            chat_id=chat_id,
            user_id=message.user_id,
            client_message_id=message.client_message_id,
            content=message.content,
            reply_to_message_id=reply_target.message_id,
        )
    )

    assert result.reply_to_message_id == reply_target.message_id
    assert result.reply_preview is not None
    assert result.reply_preview.message_id == reply_target.message_id
    assert result.reply_preview.content_preview == reply_target.content


@pytest.mark.asyncio
async def test_create_message_accepts_owned_ready_assets() -> None:
    chat_id = uuid.uuid4()
    asset_id = uuid.uuid4()
    message = _Message(chat_id=chat_id)
    repository = _Repository(message)
    asset_repository = _AssetRepository({
        asset_id: _Asset(asset_id=asset_id, owner_id=message.user_id),
    })
    service = MessageService(
        repository,  # type: ignore[arg-type]
        asset_repository=asset_repository,  # type: ignore[arg-type]
    )

    result = await service.create_message(
        MessageCreate(
            chat_id=chat_id,
            user_id=message.user_id,
            client_message_id=message.client_message_id,
            content="",
            asset_ids=[asset_id],
        )
    )

    assert result.message_id == message.message_id
    assert repository.created_asset_ids == [asset_id]


@pytest.mark.asyncio
async def test_create_message_rejects_foreign_or_unready_assets() -> None:
    chat_id = uuid.uuid4()
    asset_id = uuid.uuid4()
    message = _Message(chat_id=chat_id)
    repository = _Repository(message)
    asset_repository = _AssetRepository({
        asset_id: _Asset(
            asset_id=asset_id,
            owner_id=message.user_id,
            status=AssetStatusEnum.PENDING_UPLOAD,
        ),
    })
    service = MessageService(
        repository,  # type: ignore[arg-type]
        asset_repository=asset_repository,  # type: ignore[arg-type]
    )

    with pytest.raises(InvalidMessageAssets):
        await service.create_message(
            MessageCreate(
                chat_id=chat_id,
                user_id=message.user_id,
                client_message_id=message.client_message_id,
                content="",
                asset_ids=[asset_id],
            )
        )


@pytest.mark.asyncio
async def test_create_message_rejects_reply_in_another_chat() -> None:
    chat_id = uuid.uuid4()
    reply_target = _Message(chat_id=uuid.uuid4())
    message = _Message(chat_id=chat_id, reply_to_message=reply_target)
    service = MessageService(_Repository(message))  # type: ignore[arg-type]

    with pytest.raises(InvalidMessageReply):
        await service.create_message(
            MessageCreate(
                chat_id=chat_id,
                user_id=message.user_id,
                client_message_id=message.client_message_id,
                content=message.content,
                reply_to_message_id=reply_target.message_id,
            )
        )


@pytest.mark.asyncio
async def test_reply_preview_uses_deleted_stub() -> None:
    chat_id = uuid.uuid4()
    reply_target = _Message(
        chat_id=chat_id,
        deleted_at=datetime.datetime.now(datetime.timezone.utc),
    )
    message = _Message(chat_id=chat_id, reply_to_message=reply_target)
    service = MessageService(_Repository(message))  # type: ignore[arg-type]

    result = await service.create_message(
        MessageCreate(
            chat_id=chat_id,
            user_id=message.user_id,
            client_message_id=message.client_message_id,
            content=message.content,
            reply_to_message_id=reply_target.message_id,
        )
    )

    assert result.reply_preview is not None
    assert result.reply_preview.deleted is True
    assert result.reply_preview.content_preview == DELETED_MESSAGE_STUB


@pytest.mark.asyncio
async def test_share_content_to_chats_creates_message_per_chat() -> None:
    chat_ids = [uuid.uuid4(), uuid.uuid4()]
    content_id = uuid.uuid4()
    user_id = uuid.uuid4()
    message = _Message(chat_id=chat_ids[0])
    repository = _Repository(message)
    content_service = _ContentService()
    service = MessageService(
        repository,  # type: ignore[arg-type]
        chat_repository=_ChatRepository(chat_ids),  # type: ignore[arg-type]
        content_service=content_service,  # type: ignore[arg-type]
    )

    result = await service.share_content_to_chats(
        data=SharedContentMessagesCreate(content_id=content_id, chat_ids=chat_ids),
        user_id=user_id,
    )

    assert len(result) == 2
    assert content_service.checked == [(content_id, user_id)]
    assert [data["chat_id"] for data, _content_id in repository.created_messages] == chat_ids
    assert [shared_content_id for _data, shared_content_id in repository.created_messages] == [
        content_id,
        content_id,
    ]


@pytest.mark.asyncio
async def test_create_message_reuses_validated_shared_content_preview() -> None:
    content_id = uuid.uuid4()
    message = _Message(shared_content=_SharedContentWithoutLoadedContent(content_id))
    content_service = _ContentService(
        make_content_item(content_id=content_id, my_reaction=ReactionTypeEnum.LIKE)
    )
    service = MessageService(
        _Repository(message),  # type: ignore[arg-type]
        content_service=content_service,  # type: ignore[arg-type]
    )

    result = await service.create_message(
        MessageCreate(
            chat_id=message.chat_id,
            user_id=message.user_id,
            content=message.content,
            shared_content_id=content_id,
        )
    )

    assert content_service.checked == [(content_id, message.user_id)]
    assert result.shared_content is not None
    assert result.shared_content.my_reaction == ReactionTypeEnum.LIKE


@pytest.mark.asyncio
async def test_share_content_to_chats_reuses_single_shared_content_preview() -> None:
    chat_ids = [uuid.uuid4(), uuid.uuid4()]
    content_id = uuid.uuid4()
    user_id = uuid.uuid4()
    message = _Message(
        chat_id=chat_ids[0],
        shared_content=_SharedContentWithoutLoadedContent(content_id),
    )
    content_service = _ContentService(
        make_content_item(content_id=content_id, my_reaction=ReactionTypeEnum.LIKE)
    )
    service = MessageService(
        _Repository(message),  # type: ignore[arg-type]
        chat_repository=_ChatRepository(chat_ids),  # type: ignore[arg-type]
        content_service=content_service,  # type: ignore[arg-type]
    )

    result = await service.share_content_to_chats(
        data=SharedContentMessagesCreate(content_id=content_id, chat_ids=chat_ids),
        user_id=user_id,
    )

    assert content_service.checked == [(content_id, user_id)]
    assert [message.shared_content for message in result] == [
        content_service.result,
        content_service.result,
    ]


@pytest.mark.asyncio
async def test_share_content_to_chats_rejects_non_member_chat() -> None:
    allowed_chat_id = uuid.uuid4()
    denied_chat_id = uuid.uuid4()
    service = MessageService(
        _Repository(_Message()),  # type: ignore[arg-type]
        chat_repository=_ChatRepository([allowed_chat_id]),  # type: ignore[arg-type]
        content_service=_ContentService(),  # type: ignore[arg-type]
    )

    with pytest.raises(PermissionDenied):
        await service.share_content_to_chats(
            data=SharedContentMessagesCreate(
                content_id=uuid.uuid4(),
                chat_ids=[allowed_chat_id, denied_chat_id],
            ),
            user_id=uuid.uuid4(),
        )


@pytest.mark.asyncio
async def test_shared_content_preview_uses_viewer_reaction_from_content_service() -> None:
    content_id = uuid.uuid4()
    viewer_id = uuid.uuid4()
    message = _Message(shared_content=_SharedContentWithoutLoadedContent(content_id))
    content_service = _ContentService(
        make_content_item(content_id=content_id, my_reaction=ReactionTypeEnum.LIKE)
    )
    service = MessageService(
        _Repository(message),  # type: ignore[arg-type]
        content_service=content_service,  # type: ignore[arg-type]
    )

    result = await service._build_message_with_user(message, viewer_id=viewer_id)

    assert content_service.checked == [(content_id, viewer_id)]
    assert result.shared_content is not None
    assert result.shared_content.my_reaction == ReactionTypeEnum.LIKE


def test_search_messages_trims_query_before_querying_repository() -> None:
    chat_id = uuid.uuid4()
    message = _Message(chat_id=chat_id)
    repository = _Repository(message)
    service = MessageService(repository)  # type: ignore[arg-type]

    result = asyncio.run(
        service.search_messages(
            chat_id=chat_id,
            viewer_id=message.user_id,
            query="  hello world  ",
            order="created_at",
            order_desc=True,
            offset=0,
            limit=20,
        )
    )

    assert result.total == 3
    assert result.offset == 0
    assert result.limit == 20
    assert result.items[0].message_id == message.message_id
    assert repository.search_calls[0]["query_text"] == "hello world"
