from __future__ import annotations

import datetime
import typing as tp
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, Index, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.activity.enums import ActivityActionTypeEnum
from src.common.models import Base
from src.content.enums import ContentTypeEnum


def _enum_values(enum_cls):  # type: ignore[no-untyped-def]
    return [item.value for item in enum_cls]


class ActivityEventModel(Base):
    __tablename__ = "user_activity_events"
    __table_args__ = (
        Index("ix_user_activity_events_user_created_at", "user_id", text("created_at DESC")),
        Index("ix_user_activity_events_user_action_created_at", "user_id", "action_type", text("created_at DESC")),
        Index("ix_user_activity_events_user_content_type_created_at", "user_id", "content_type", text("created_at DESC")),
        Index("ix_user_activity_events_content_created_at", "content_id", text("created_at DESC")),
        Index("ix_user_activity_events_target_user_created_at", "target_user_id", text("created_at DESC")),
    )

    activity_event_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    action_type: Mapped[ActivityActionTypeEnum] = mapped_column(
        Enum(
            ActivityActionTypeEnum,
            name="activity_action_type_enum",
            values_callable=_enum_values,
        ),
        nullable=False,
    )
    content_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("content.content_id", ondelete="SET NULL"),
        nullable=True,
    )
    target_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    comment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("comments.comment_id", ondelete="SET NULL"),
        nullable=True,
    )
    content_type: Mapped[ContentTypeEnum | None] = mapped_column(
        Enum(ContentTypeEnum, name="content_type_enum", values_callable=_enum_values),
        nullable=True,
    )
    event_metadata: Mapped[dict[str, tp.Any]] = mapped_column(
        "metadata",
        JSONB,
        default=dict,
        server_default=text("'{}'::jsonb"),
        nullable=False,
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        server_default=text("now()"),
        nullable=False,
    )

    user: Mapped["UserModel"] = relationship(  # type: ignore[name-defined]
        foreign_keys=[user_id],
        passive_deletes=True,
    )
    content: Mapped["ContentModel | None"] = relationship(  # type: ignore[name-defined]
        foreign_keys=[content_id],
        passive_deletes=True,
    )
    target_user: Mapped["UserModel | None"] = relationship(  # type: ignore[name-defined]
        foreign_keys=[target_user_id],
        passive_deletes=True,
    )
    comment: Mapped["CommentModel | None"] = relationship(  # type: ignore[name-defined]
        foreign_keys=[comment_id],
        passive_deletes=True,
    )
