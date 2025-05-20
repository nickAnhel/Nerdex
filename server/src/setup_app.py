from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import settings

# Routes
from src.users.router import router as users_router
from src.auth.router import router as auth_router
from src.posts.router import router as posts_router
from src.chats.router import router as chats_router
from src.messages.router import router as messages_router
from src.events.router import router as events_router

# Exception handlers
from src.exceptions import (
    PermissionDenied,
)
from src.exc_handlers import (
    permission_denied_handler,
)

from src.users.exc_handlers import (
    user_not_found_handler,
    username_or_email_already_exists_handler,
    cant_subscribe_to_user_handler,
    cant_unsubscribe_from_user_handler,
    user_not_in_subscriptions_handler,
)
from src.users.exceptions import (
    UserNotFound,
    UsernameOrEmailAlreadyExists,
    CantSubscribeToUser,
    CantUnsubscribeFromUser,
    UserNotInSubscriptions,
)

from src.posts.exc_handlers import (
    post_not_found_handler,
    post_already_rated_handler,
)
from src.posts.exceptions import (
    PostNotFound,
    PostAlreadyRated,
)

from src.chats.exc_handlers import (
    chat_not_found_handler,
    already_in_chat_handler,
    cant_add_members_handler,
    cant_remove_members_handler,
    failed_to_leave_chat_handler,
)
from src.chats.exceptions import (
    ChatNotFound,
    AlreadyInChat,
    CantAddMembers,
    CantRemoveMembers,
    FailedToLeaveChat,
)

from src.messages.exc_handlers import (
    cant_delete_message_handler,
    cant_update_message_handler,
)
from src.messages.exceptions import (
    CantDeleteMessage,
    CantUpdateMessage,
)


def register_routes(app: FastAPI) -> None:
    app.include_router(auth_router)
    app.include_router(users_router)
    app.include_router(posts_router)
    app.include_router(chats_router)
    app.include_router(messages_router)
    app.include_router(events_router)


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(PermissionDenied, permission_denied_handler)  # type: ignore

    app.add_exception_handler(UserNotFound, user_not_found_handler)  # type: ignore
    app.add_exception_handler(
        UsernameOrEmailAlreadyExists,
        username_or_email_already_exists_handler,  # type: ignore
    )
    app.add_exception_handler(CantSubscribeToUser, cant_subscribe_to_user_handler)  # type: ignore
    app.add_exception_handler(CantUnsubscribeFromUser, cant_unsubscribe_from_user_handler)  # type: ignore
    app.add_exception_handler(UserNotInSubscriptions, user_not_in_subscriptions_handler)  # type: ignore

    app.add_exception_handler(PostNotFound, post_not_found_handler)  # type: ignore
    app.add_exception_handler(PostAlreadyRated, post_already_rated_handler)  # type: ignore

    app.add_exception_handler(ChatNotFound, chat_not_found_handler)  # type: ignore
    app.add_exception_handler(AlreadyInChat, already_in_chat_handler)  # type: ignore
    app.add_exception_handler(CantAddMembers, cant_add_members_handler)  # type: ignore
    app.add_exception_handler(CantRemoveMembers, cant_remove_members_handler)  # type: ignore
    app.add_exception_handler(FailedToLeaveChat, failed_to_leave_chat_handler)  # type: ignore

    app.add_exception_handler(CantDeleteMessage, cant_delete_message_handler)  # type: ignore
    app.add_exception_handler(CantUpdateMessage, cant_update_message_handler)  # type: ignore


def register_middleware(app: FastAPI) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors.allowed_hosts,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def setup_app(app: FastAPI) -> None:
    register_routes(app)
    register_exception_handlers(app)
    register_middleware(app)
