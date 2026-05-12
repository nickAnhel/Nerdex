"""add chat timeline items

Revision ID: 5e6f7a8b9c0d
Revises: 9a0b1c2d3e4f
Create Date: 2026-05-12 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "5e6f7a8b9c0d"
down_revision: Union[str, None] = "9a0b1c2d3e4f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "chats",
        sa.Column(
            "last_timeline_seq",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.create_table(
        "chat_timeline_items",
        sa.Column("chat_id", sa.Uuid(), nullable=False),
        sa.Column("chat_seq", sa.BigInteger(), nullable=False),
        sa.Column("item_type", sa.String(), nullable=False),
        sa.Column("message_id", sa.Uuid(), nullable=True),
        sa.Column("event_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "item_type in ('message', 'event')",
            name="ck_chat_timeline_items_item_type",
        ),
        sa.CheckConstraint(
            """
            (
                item_type = 'message'
                and message_id is not null
                and event_id is null
            )
            or
            (
                item_type = 'event'
                and event_id is not null
                and message_id is null
            )
            """,
            name="ck_chat_timeline_items_single_ref",
        ),
        sa.ForeignKeyConstraint(
            ["chat_id"],
            ["chats.chat_id"],
            name="fk_chat_timeline_items_chat_id_chats",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["messages.message_id"],
            name="fk_chat_timeline_items_message_id_messages",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["events.event_id"],
            name="fk_chat_timeline_items_event_id_events",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "chat_id",
            "chat_seq",
            name="pk_chat_timeline_items",
        ),
        sa.UniqueConstraint(
            "message_id",
            name="uq_chat_timeline_items_message_id",
        ),
        sa.UniqueConstraint(
            "event_id",
            name="uq_chat_timeline_items_event_id",
        ),
    )
    op.create_index(
        "ix_chat_timeline_items_chat_seq",
        "chat_timeline_items",
        ["chat_id", "chat_seq"],
    )

    op.execute(
        """
        with source_items as (
            select
                messages.chat_id,
                'message'::text as item_type,
                messages.message_id,
                null::uuid as event_id,
                messages.created_at,
                0 as item_rank,
                messages.message_id::text as item_id
            from messages
            union all
            select
                events.chat_id,
                'event'::text as item_type,
                null::uuid as message_id,
                events.event_id,
                events.created_at,
                1 as item_rank,
                events.event_id::text as item_id
            from events
        ),
        ranked_items as (
            select
                chat_id,
                row_number() over (
                    partition by chat_id
                    order by created_at asc, item_rank asc, item_id asc
                ) as chat_seq,
                item_type,
                message_id,
                event_id
            from source_items
        )
        insert into chat_timeline_items (
            chat_id,
            chat_seq,
            item_type,
            message_id,
            event_id
        )
        select
            chat_id,
            chat_seq,
            item_type,
            message_id,
            event_id
        from ranked_items
        """
    )
    op.execute(
        """
        update chats
        set last_timeline_seq = timeline.max_seq
        from (
            select chat_id, max(chat_seq) as max_seq
            from chat_timeline_items
            group by chat_id
        ) as timeline
        where chats.chat_id = timeline.chat_id
        """
    )


def downgrade() -> None:
    op.drop_index("ix_chat_timeline_items_chat_seq", table_name="chat_timeline_items")
    op.drop_table("chat_timeline_items")
    op.drop_column("chats", "last_timeline_seq")
