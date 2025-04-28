from sqladmin import ModelView

from src.admin.models import SessionModel
from src.posts.models import PostModel
from src.users.models import UserModel


class UserAdminView(ModelView, model=UserModel):
    column_list = ["user_id", "username", "is_admin"]
    column_searchable_list = ["user_id", "username"]
    column_details_exclude_list = ["hashed_password"]


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
    column_sortable_list = ["issued_at", "expires_at"]
