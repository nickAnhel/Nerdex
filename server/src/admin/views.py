from sqladmin import ModelView

from src.admin.models import SessionModel
from src.chats.models import ChatModel, MembershipModel
from src.events.models import EventModel
from src.messages.models import MessageModel
from src.posts.models import PostModel
from src.users.models import UserModel


class UserAdminView(ModelView, model=UserModel):
    column_list = ["user_id", "username", "is_admin", "subscribers_count"]
    column_searchable_list = ["user_id", "username"]
    column_details_exclude_list = ["hashed_password"]
    can_create = False
    can_delete = False


class PostAdminView(ModelView, model=PostModel):
    column_list = [
        "post_id",
        "user_id",
        "content_ellipsis",
        "likes",
        "dislikes",
        "created_at",
    ]
    column_searchable_list = ["post_id"]


class SessionAdminView(ModelView, model=SessionModel):
    column_list = ["session_id", "user_id", "issued_at", "expires_at"]
    column_sortable_list = ["session_id", "issued_at", "expires_at"]


class ChatAdminView(ModelView, model=ChatModel):
    column_list = ["chat_id", "title", "is_private", "owner_id"]
    column_searchable_list = ["chat_id", "title"]


class MembershipAdminView(ModelView, model=MembershipModel):
    column_list = ["chat_id", "user_id"]
    can_create = False
    can_delete = False
    can_edit = False


class MessageAdminView(ModelView, model=MessageModel):
    column_list = ["message_id", "chat_id", "content_ellipsis"]
    column_searchable_list = ["messag_id", "content"]
    can_delete = False
    can_edit = False


class EventAdminView(ModelView, model=EventModel):
    column_list = ["event_id", "chat_id", "user_id", "event_type", "created_at"]
    column_searchable_list = ["event_id", "event_type"]
