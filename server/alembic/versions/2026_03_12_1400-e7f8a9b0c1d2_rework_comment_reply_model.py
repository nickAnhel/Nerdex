"""Rework comment reply model

Revision ID: e7f8a9b0c1d2
Revises: d2c3b4a5f6e7
Create Date: 2026-03-12 14:00:00.000000

"""

from __future__ import annotations

from collections import defaultdict
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e7f8a9b0c1d2"
down_revision: Union[str, None] = "d2c3b4a5f6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _normalize_legacy_comment(
    comment_id,
    comments_by_id,
):
    comment = comments_by_id[comment_id]
    depth = comment["depth"]

    if depth == 0:
        return {
            "parent_comment_id": None,
            "root_comment_id": None,
            "reply_to_comment_id": None,
            "depth": 0,
        }

    parent_comment_id = comment["parent_comment_id"]
    if parent_comment_id is None:
        raise ValueError("Legacy reply must reference a parent comment")

    if depth == 1:
        return {
            "parent_comment_id": parent_comment_id,
            "root_comment_id": parent_comment_id,
            "reply_to_comment_id": parent_comment_id,
            "depth": 1,
        }

    display_parent = comments_by_id.get(parent_comment_id)
    if display_parent is None:
        raise ValueError("Legacy comment parent could not be resolved")

    semantic_target_id = display_parent["comment_id"]
    while display_parent["depth"] > 1:
        ancestor_parent_id = display_parent["parent_comment_id"]
        if ancestor_parent_id is None:
            raise ValueError("Legacy depth >= 2 comment has no depth 1 ancestor")
        display_parent = comments_by_id.get(ancestor_parent_id)
        if display_parent is None:
            raise ValueError("Legacy depth 1 ancestor could not be resolved")

    if display_parent["depth"] != 1 or display_parent["parent_comment_id"] is None:
        raise ValueError("Legacy comment did not resolve to a valid depth 1 ancestor")

    return {
        "parent_comment_id": display_parent["comment_id"],
        "root_comment_id": display_parent["parent_comment_id"],
        "reply_to_comment_id": semantic_target_id,
        "depth": 2,
    }


def upgrade() -> None:
    comments = sa.table(
        "comments",
        sa.column("comment_id", sa.Uuid()),
        sa.column("content_id", sa.Uuid()),
        sa.column("parent_comment_id", sa.Uuid()),
        sa.column("root_comment_id", sa.Uuid()),
        sa.column("reply_to_comment_id", sa.Uuid()),
        sa.column("depth", sa.Integer()),
        sa.column("deleted_at", sa.DateTime(timezone=True)),
        sa.column("replies_count", sa.Integer()),
    )
    content = sa.table(
        "content",
        sa.column("content_id", sa.Uuid()),
        sa.column("comments_count", sa.Integer()),
    )

    op.add_column("comments", sa.Column("reply_to_comment_id", sa.Uuid(), nullable=True))

    bind = op.get_bind()
    rows = list(
        bind.execute(
            sa.select(
                comments.c.comment_id,
                comments.c.content_id,
                comments.c.parent_comment_id,
                comments.c.root_comment_id,
                comments.c.depth,
                comments.c.deleted_at,
            )
        )
    )

    if rows:
        comments_by_id = {
            row.comment_id: {
                "comment_id": row.comment_id,
                "content_id": row.content_id,
                "parent_comment_id": row.parent_comment_id,
                "root_comment_id": row.root_comment_id,
                "depth": row.depth,
                "deleted_at": row.deleted_at,
            }
            for row in rows
        }

        migrated_comments: dict[object, dict[str, object | None]] = {}
        for row in rows:
            placement = _normalize_legacy_comment(row.comment_id, comments_by_id)
            migrated_comments[row.comment_id] = {
                "comment_id": row.comment_id,
                "content_id": row.content_id,
                "parent_comment_id": placement["parent_comment_id"],
                "root_comment_id": placement["root_comment_id"],
                "reply_to_comment_id": placement["reply_to_comment_id"],
                "depth": placement["depth"],
                "deleted_at": row.deleted_at,
                "replies_count": 0,
            }

        children_by_parent: dict[object, list[dict[str, object | None]]] = defaultdict(list)
        for migrated_comment in migrated_comments.values():
            parent_comment_id = migrated_comment["parent_comment_id"]
            if parent_comment_id is not None:
                children_by_parent[parent_comment_id].append(migrated_comment)

        for migrated_comment in migrated_comments.values():
            if migrated_comment["depth"] == 1:
                migrated_comment["replies_count"] = sum(
                    1
                    for child in children_by_parent.get(migrated_comment["comment_id"], [])
                    if child["deleted_at"] is None
                )

        for migrated_comment in migrated_comments.values():
            if migrated_comment["depth"] == 0:
                migrated_comment["replies_count"] = sum(
                    1
                    for child in children_by_parent.get(migrated_comment["comment_id"], [])
                    if child["deleted_at"] is None or (child["replies_count"] or 0) > 0
                )

        for migrated_comment in migrated_comments.values():
            bind.execute(
                sa.update(comments)
                .where(comments.c.comment_id == migrated_comment["comment_id"])
                .values(
                    parent_comment_id=migrated_comment["parent_comment_id"],
                    root_comment_id=migrated_comment["root_comment_id"],
                    reply_to_comment_id=migrated_comment["reply_to_comment_id"],
                    depth=migrated_comment["depth"],
                    replies_count=migrated_comment["replies_count"],
                )
            )

        bind.execute(sa.update(content).values(comments_count=0))
        content_comments_count: dict[object, int] = defaultdict(int)
        for migrated_comment in migrated_comments.values():
            if migrated_comment["deleted_at"] is None:
                content_comments_count[migrated_comment["content_id"]] += 1

        for content_id, comments_count in content_comments_count.items():
            bind.execute(
                sa.update(content)
                .where(content.c.content_id == content_id)
                .values(comments_count=comments_count)
            )

    op.create_foreign_key(
        "fk_comments_reply_to_comment_id_comments",
        "comments",
        "comments",
        ["reply_to_comment_id"],
        ["comment_id"],
        ondelete="CASCADE",
    )
    op.drop_constraint("ck_comments_depth_non_negative", "comments", type_="check")
    op.create_check_constraint("ck_comments_depth_range", "comments", "depth BETWEEN 0 AND 2")


def downgrade() -> None:
    op.drop_constraint("ck_comments_depth_range", "comments", type_="check")
    op.create_check_constraint("ck_comments_depth_non_negative", "comments", "depth >= 0")
    op.drop_constraint("fk_comments_reply_to_comment_id_comments", "comments", type_="foreignkey")
    op.drop_column("comments", "reply_to_comment_id")
