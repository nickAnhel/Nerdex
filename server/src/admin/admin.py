from sqladmin import Admin

from src.admin.auth import AdminAuth
from src.admin.views import (
    ChatAdminView,
    EventAdminView,
    MembershipAdminView,
    MessageAdminView,
    PostAdminView,
    SessionAdminView,
    UserAdminView,
)
from src.config import settings
from src.database import async_engine


def create_admin(app) -> Admin:
    admin = Admin(
        app=app,
        engine=async_engine,
        authentication_backend=AdminAuth(secret_key=settings.admin.secret_key),
    )

    admin.add_model_view(UserAdminView)
    admin.add_model_view(PostAdminView)
    admin.add_model_view(ChatAdminView)
    admin.add_model_view(MembershipAdminView)
    admin.add_model_view(MessageAdminView)
    admin.add_model_view(EventAdminView)
    admin.add_model_view(SessionAdminView)

    return admin
