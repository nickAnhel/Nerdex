import datetime
import uuid
from typing import Annotated

from pydantic import Field, model_validator

from src.chats.enums import ChatType
from src.events.schemas import EventGetWithUsers
from src.messages.schemas import MessageGetWithUser
from src.common.schemas import BaseSchema
from src.users.schemas import UserAvatarGet, UserGet

TitleStr = Annotated[str, Field(min_length=1, max_length=64)]


class ChatCreate(BaseSchema):
    chat_type: ChatType = ChatType.GROUP
    title: TitleStr | None = None
    is_private: bool = False
    member_id: uuid.UUID | None = None
    members: list[uuid.UUID] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_payload(self) -> "ChatCreate":
        if self.chat_type == ChatType.DIRECT:
            if self.member_id is None:
                raise ValueError("member_id is required for direct chats")
            return self

        if self.title is None or not self.title.strip():
            raise ValueError("title is required for group chats")
        return self


class ChatGet(BaseSchema):
    chat_id: uuid.UUID
    title: TitleStr
    is_private: bool
    chat_type: ChatType
    owner_id: uuid.UUID
    members: list[UserGet] = Field(default_factory=list)


class ChatDialogGet(ChatGet):
    display_title: str
    display_avatar: UserAvatarGet | None = None
    last_message: MessageGetWithUser | None = None
    last_message_at: datetime.datetime | None = None
    unread_count: int = 0
    is_muted: bool = False
    last_read_message_id: uuid.UUID | None = None


class ChatUpdate(BaseSchema):
    title: TitleStr | None = None
    is_private: bool | None = None


class MessageHistoryItem(MessageGetWithUser):
    item_type: str = "message"
    chat_seq: int


class EventHistoryItem(EventGetWithUsers):
    item_type: str = "event"
    chat_seq: int
