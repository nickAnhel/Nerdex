import datetime
import uuid

from pydantic import BaseModel, Field, model_validator

from src.assets.enums import AssetTypeEnum
from src.common.schemas import BaseSchema
from src.users.schemas import UserGet


class MessageCreateWS(BaseModel):
    chat_id: uuid.UUID
    client_message_id: uuid.UUID
    content: str = Field(default="", max_length=4096)
    reply_to_message_id: uuid.UUID | None = None
    asset_ids: list[uuid.UUID] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def validate_content_or_assets(self) -> "MessageCreateWS":
        if not self.content.strip() and not self.asset_ids:
            raise ValueError("Message must contain text or attachments")
        return self


class MessageReplyPreview(BaseModel):
    message_id: uuid.UUID
    sender_display_name: str
    content_preview: str
    deleted: bool


class MessageAttachmentGet(BaseModel):
    asset_id: uuid.UUID
    position: int = Field(ge=0)
    asset_type: AssetTypeEnum
    mime_type: str | None = None
    file_kind: str
    original_filename: str | None = None
    size_bytes: int | None = Field(default=None, ge=0)
    width: int | None = Field(default=None, ge=0)
    height: int | None = Field(default=None, ge=0)
    duration_ms: int | None = Field(default=None, ge=0)
    preview_url: str | None = None
    original_url: str | None = None
    poster_url: str | None = None
    download_url: str | None = None
    stream_url: str | None = None
    is_audio: bool = False


class MessageGetWS(BaseModel):
    message_id: uuid.UUID
    chat_id: uuid.UUID
    client_message_id: uuid.UUID | None = None
    item_type: str = "message"
    chat_seq: int | None = None
    content: str
    created_at: datetime.datetime
    edited_at: datetime.datetime | None = None
    deleted_at: datetime.datetime | None = None
    deleted_by: uuid.UUID | None = None
    reply_to_message_id: uuid.UUID | None = None
    reply_preview: MessageReplyPreview | None = None
    username: str
    user_id: uuid.UUID
    avatar_small_url: str | None = None
    attachments: list[MessageAttachmentGet] = Field(default_factory=list)


class MessageUpdateWS(BaseModel):
    message_id: uuid.UUID
    content: str


class MessageDeleteWS(BaseModel):
    message_id: uuid.UUID


class MessageCreate(BaseSchema):
    chat_id: uuid.UUID
    client_message_id: uuid.UUID | None = None
    content: str = Field(default="", max_length=4096)
    user_id: uuid.UUID
    reply_to_message_id: uuid.UUID | None = None
    asset_ids: list[uuid.UUID] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def validate_content_or_assets(self) -> "MessageCreate":
        if type(self) is MessageCreate and not self.content.strip() and not self.asset_ids:
            raise ValueError("Message must contain text or attachments")
        return self


class MessageGet(MessageCreate):
    message_id: uuid.UUID
    created_at: datetime.datetime
    edited_at: datetime.datetime | None = None
    deleted_at: datetime.datetime | None = None
    deleted_by: uuid.UUID | None = None
    chat_seq: int | None = None
    reply_preview: MessageReplyPreview | None = None
    attachments: list[MessageAttachmentGet] = Field(default_factory=list)


class MessageGetWithUser(MessageGet):
    user: UserGet


class MessageUpdate(BaseSchema):
    content: str | None = None
