import datetime
import uuid

import pytest
from sqlalchemy.exc import NoResultFound

from src.assets.enums import AssetStatusEnum, AssetVariantStatusEnum, AssetVariantTypeEnum
from src.messages.exceptions import CantDeleteMessage, CantUpdateMessage, InvalidMessageAssets, InvalidMessageReply
from src.messages.schemas import MessageCreate, MessageUpdate
from src.messages.service import DELETED_MESSAGE_STUB, MessageService


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
    def __init__(self, *, chat_id=None, deleted_at=None, reply_to_message=None) -> None:
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

    @property
    def content_ellipsis(self) -> str:
        return self.content


class _Repository:
    def __init__(self, message=None, *, raises=None) -> None:
        self.message = message
        self.raises = raises
        self.created_asset_ids = None

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
