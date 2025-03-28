from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import settings

# Routes
from src.users.router import router as users_router
from src.auth.router import router as auth_router

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
)
from src.users.exceptions import (
    UserNotFound,
    UsernameOrEmailAlreadyExists,
)


def register_routes(app: FastAPI) -> None:
    app.include_router(auth_router)
    app.include_router(users_router)


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(PermissionDenied, permission_denied_handler)  # type: ignore

    app.add_exception_handler(UserNotFound, user_not_found_handler)  # type: ignore
    app.add_exception_handler(UsernameOrEmailAlreadyExists, username_or_email_already_exists_handler)  # type: ignore


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
