from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import settings

# WebSockets
from src.chats.sockets import socket_app as ws_app

# Routes
from src.users.router import router as users_router
from src.auth.router import router as auth_router
from src.posts.router import router as posts_router
from src.articles.router import router as articles_router
from src.comments.router import router as comments_router
from src.tags.router import router as tags_router
from src.content.router import router as content_router
from src.chats.router import router as chats_router
from src.messages.router import router as messages_router
from src.events.router import router as events_router
from src.assets.router import router as assets_router
from src.videos.router import router as videos_router

# Exception handlers
from src.common.exceptions import (
    PermissionDenied,
)
from src.common.exc_handlers import (
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
    UsernameAlreadyExists,
    CantSubscribeToUser,
    CantUnsubscribeFromUser,
    UserNotInSubscriptions,
)

from src.posts.exc_handlers import invalid_post_handler, post_not_found_handler
from src.posts.exceptions import InvalidPost, PostNotFound
from src.articles.exc_handlers import article_not_found_handler, invalid_article_handler
from src.articles.exceptions import ArticleNotFound, InvalidArticle
from src.comments.exc_handlers import comment_not_found_handler, invalid_comment_handler
from src.comments.exceptions import CommentNotFound, InvalidComment
from src.tags.exc_handlers import invalid_tag_handler
from src.tags.exceptions import InvalidTag

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

from src.s3.exc_handlers import (
    cant_delete_file_handler,
    cant_upload_file_handler,
)
from src.s3.exceptions import (
    CantDeleteFileFromStorage,
    CantUploadFileToStorage,
)
from src.assets.exc_handlers import (
    asset_not_found_handler,
    asset_upload_not_ready_handler,
    invalid_asset_handler,
)
from src.assets.exceptions import (
    AssetNotFound,
    AssetUploadNotReady,
    InvalidAsset,
)
from src.videos.exc_handlers import invalid_video_handler, video_not_found_handler
from src.videos.exceptions import InvalidVideo, VideoNotFound


def register_routes(app: FastAPI) -> None:
    app.include_router(auth_router)
    app.include_router(users_router)
    app.include_router(posts_router)
    app.include_router(articles_router)
    app.include_router(comments_router)
    app.include_router(tags_router)
    app.include_router(content_router)
    app.include_router(chats_router)
    app.include_router(messages_router)
    app.include_router(events_router)
    app.include_router(assets_router)
    app.include_router(videos_router)

    app.mount("/ws", ws_app)


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(PermissionDenied, permission_denied_handler)  # type: ignore

    app.add_exception_handler(UserNotFound, user_not_found_handler)  # type: ignore
    app.add_exception_handler(
        UsernameAlreadyExists,
        username_or_email_already_exists_handler,  # type: ignore
    )
    app.add_exception_handler(CantSubscribeToUser, cant_subscribe_to_user_handler)  # type: ignore
    app.add_exception_handler(CantUnsubscribeFromUser, cant_unsubscribe_from_user_handler)  # type: ignore
    app.add_exception_handler(UserNotInSubscriptions, user_not_in_subscriptions_handler)  # type: ignore

    app.add_exception_handler(PostNotFound, post_not_found_handler)  # type: ignore
    app.add_exception_handler(InvalidPost, invalid_post_handler)  # type: ignore
    app.add_exception_handler(ArticleNotFound, article_not_found_handler)  # type: ignore
    app.add_exception_handler(InvalidArticle, invalid_article_handler)  # type: ignore
    app.add_exception_handler(CommentNotFound, comment_not_found_handler)  # type: ignore
    app.add_exception_handler(InvalidComment, invalid_comment_handler)  # type: ignore
    app.add_exception_handler(InvalidTag, invalid_tag_handler)  # type: ignore

    app.add_exception_handler(ChatNotFound, chat_not_found_handler)  # type: ignore
    app.add_exception_handler(AlreadyInChat, already_in_chat_handler)  # type: ignore
    app.add_exception_handler(CantAddMembers, cant_add_members_handler)  # type: ignore
    app.add_exception_handler(CantRemoveMembers, cant_remove_members_handler)  # type: ignore
    app.add_exception_handler(FailedToLeaveChat, failed_to_leave_chat_handler)  # type: ignore

    app.add_exception_handler(CantDeleteMessage, cant_delete_message_handler)  # type: ignore
    app.add_exception_handler(CantUpdateMessage, cant_update_message_handler)  # type: ignore

    app.add_exception_handler(CantDeleteFileFromStorage, cant_delete_file_handler)  # type: ignore
    app.add_exception_handler(CantUploadFileToStorage, cant_upload_file_handler)  # type: ignore
    app.add_exception_handler(AssetNotFound, asset_not_found_handler)  # type: ignore
    app.add_exception_handler(InvalidAsset, invalid_asset_handler)  # type: ignore
    app.add_exception_handler(AssetUploadNotReady, asset_upload_not_ready_handler)  # type: ignore
    app.add_exception_handler(VideoNotFound, video_not_found_handler)  # type: ignore
    app.add_exception_handler(InvalidVideo, invalid_video_handler)  # type: ignore


def register_middleware(app: FastAPI) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors.allowed_hosts,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "Accept"],
    )


def setup_app(app: FastAPI) -> None:
    register_routes(app)
    register_exception_handlers(app)
    register_middleware(app)
