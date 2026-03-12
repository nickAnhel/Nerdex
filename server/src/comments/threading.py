from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Mapping


MAX_COMMENT_DEPTH = 2


@dataclass(frozen=True, slots=True)
class CommentPlacement:
    parent_comment_id: uuid.UUID | None
    root_comment_id: uuid.UUID | None
    reply_to_comment_id: uuid.UUID | None
    depth: int


@dataclass(frozen=True, slots=True)
class CommentThreadNode:
    comment_id: uuid.UUID
    parent_comment_id: uuid.UUID | None
    root_comment_id: uuid.UUID | None
    depth: int


def build_root_comment_placement() -> CommentPlacement:
    return CommentPlacement(
        parent_comment_id=None,
        root_comment_id=None,
        reply_to_comment_id=None,
        depth=0,
    )


def build_reply_placement(target: CommentThreadNode) -> CommentPlacement:
    if target.depth == 0:
        return CommentPlacement(
            parent_comment_id=target.comment_id,
            root_comment_id=target.comment_id,
            reply_to_comment_id=target.comment_id,
            depth=1,
        )

    if target.depth == 1:
        if target.root_comment_id is None:
            raise ValueError("Depth 1 comment must reference a root comment")
        return CommentPlacement(
            parent_comment_id=target.comment_id,
            root_comment_id=target.root_comment_id,
            reply_to_comment_id=target.comment_id,
            depth=2,
        )

    if target.depth == 2:
        if target.parent_comment_id is None or target.root_comment_id is None:
            raise ValueError("Depth 2 comment must reference display parent and root comment")
        return CommentPlacement(
            parent_comment_id=target.parent_comment_id,
            root_comment_id=target.root_comment_id,
            reply_to_comment_id=target.comment_id,
            depth=2,
        )

    raise ValueError(f"Comment depth cannot exceed {MAX_COMMENT_DEPTH}")


def normalize_legacy_comment(
    comment: CommentThreadNode,
    comments_by_id: Mapping[uuid.UUID, CommentThreadNode],
) -> CommentPlacement:
    if comment.depth == 0:
        return build_root_comment_placement()

    if comment.parent_comment_id is None:
        raise ValueError("Legacy reply must reference a parent comment")

    if comment.depth == 1:
        return CommentPlacement(
            parent_comment_id=comment.parent_comment_id,
            root_comment_id=comment.parent_comment_id,
            reply_to_comment_id=comment.parent_comment_id,
            depth=1,
        )

    display_parent = comments_by_id.get(comment.parent_comment_id)
    if display_parent is None:
        raise ValueError("Legacy comment parent could not be resolved")

    semantic_target_id = display_parent.comment_id
    while display_parent.depth > 1:
        if display_parent.parent_comment_id is None:
            raise ValueError("Legacy depth >= 2 comment has no depth 1 ancestor")
        display_parent = comments_by_id.get(display_parent.parent_comment_id)
        if display_parent is None:
            raise ValueError("Legacy depth 1 ancestor could not be resolved")

    if display_parent.depth != 1 or display_parent.parent_comment_id is None:
        raise ValueError("Legacy comment did not resolve to a valid depth 1 ancestor")

    return CommentPlacement(
        parent_comment_id=display_parent.comment_id,
        root_comment_id=display_parent.parent_comment_id,
        reply_to_comment_id=semantic_target_id,
        depth=2,
    )
