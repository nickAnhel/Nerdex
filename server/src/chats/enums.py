from enum import Enum


class ChatOrder(str, Enum):
    ID = "chat_id"
    TITLE = "title"


class ChatType(str, Enum):
    DIRECT = "direct"
    GROUP = "group"


class ChatMemberRole(str, Enum):
    OWNER = "owner"
    MEMBER = "member"
