import uuid

import pytest

from src.comments.threading import (
    CommentThreadNode,
    MAX_COMMENT_DEPTH,
    build_reply_placement,
    build_root_comment_placement,
    normalize_legacy_comment,
)


def make_node(
    *,
    depth: int,
    parent_comment_id: uuid.UUID | None = None,
    root_comment_id: uuid.UUID | None = None,
) -> CommentThreadNode:
    return CommentThreadNode(
        comment_id=uuid.uuid4(),
        parent_comment_id=parent_comment_id,
        root_comment_id=root_comment_id,
        depth=depth,
    )


def test_build_root_comment_placement() -> None:
    placement = build_root_comment_placement()

    assert placement.parent_comment_id is None
    assert placement.root_comment_id is None
    assert placement.reply_to_comment_id is None
    assert placement.depth == 0


def test_build_reply_placement_for_depth_zero() -> None:
    root = make_node(depth=0)

    placement = build_reply_placement(root)

    assert placement.parent_comment_id == root.comment_id
    assert placement.root_comment_id == root.comment_id
    assert placement.reply_to_comment_id == root.comment_id
    assert placement.depth == 1


def test_build_reply_placement_for_depth_one() -> None:
    root = make_node(depth=0)
    depth_one = make_node(
        depth=1,
        parent_comment_id=root.comment_id,
        root_comment_id=root.comment_id,
    )

    placement = build_reply_placement(depth_one)

    assert placement.parent_comment_id == depth_one.comment_id
    assert placement.root_comment_id == root.comment_id
    assert placement.reply_to_comment_id == depth_one.comment_id
    assert placement.depth == 2


def test_build_reply_placement_for_depth_two() -> None:
    root = make_node(depth=0)
    depth_one = make_node(
        depth=1,
        parent_comment_id=root.comment_id,
        root_comment_id=root.comment_id,
    )
    depth_two = make_node(
        depth=2,
        parent_comment_id=depth_one.comment_id,
        root_comment_id=root.comment_id,
    )

    placement = build_reply_placement(depth_two)

    assert placement.parent_comment_id == depth_one.comment_id
    assert placement.root_comment_id == root.comment_id
    assert placement.reply_to_comment_id == depth_two.comment_id
    assert placement.depth == 2


def test_build_reply_placement_rejects_depth_above_max() -> None:
    invalid = make_node(depth=MAX_COMMENT_DEPTH + 1)

    with pytest.raises(ValueError, match="cannot exceed"):
        build_reply_placement(invalid)


def test_normalize_legacy_root_comment() -> None:
    root = make_node(depth=0)

    placement = normalize_legacy_comment(root, {root.comment_id: root})

    assert placement.parent_comment_id is None
    assert placement.root_comment_id is None
    assert placement.reply_to_comment_id is None
    assert placement.depth == 0


def test_normalize_legacy_depth_one_comment() -> None:
    root = make_node(depth=0)
    depth_one = make_node(depth=1, parent_comment_id=root.comment_id)

    placement = normalize_legacy_comment(
        depth_one,
        {
            root.comment_id: root,
            depth_one.comment_id: depth_one,
        },
    )

    assert placement.parent_comment_id == root.comment_id
    assert placement.root_comment_id == root.comment_id
    assert placement.reply_to_comment_id == root.comment_id
    assert placement.depth == 1


def test_normalize_legacy_deep_comment_collapses_to_depth_two() -> None:
    root = make_node(depth=0)
    depth_one = make_node(
        depth=1,
        parent_comment_id=root.comment_id,
        root_comment_id=root.comment_id,
    )
    depth_two = make_node(
        depth=2,
        parent_comment_id=depth_one.comment_id,
        root_comment_id=root.comment_id,
    )
    depth_three = make_node(
        depth=3,
        parent_comment_id=depth_two.comment_id,
        root_comment_id=root.comment_id,
    )

    placement = normalize_legacy_comment(
        depth_three,
        {
            root.comment_id: root,
            depth_one.comment_id: depth_one,
            depth_two.comment_id: depth_two,
            depth_three.comment_id: depth_three,
        },
    )

    assert placement.parent_comment_id == depth_one.comment_id
    assert placement.root_comment_id == root.comment_id
    assert placement.reply_to_comment_id == depth_two.comment_id
    assert placement.depth == 2
