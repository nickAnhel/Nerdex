import datetime
import uuid
from collections import defaultdict
from dataclasses import dataclass

import pytest

from src.comments.exceptions import CommentNotFound, InvalidComment
from src.comments.repository import (
    CommentAuthorRow,
    CommentPageResult,
    CommentParentRefRow,
    CommentRatingRow,
    CommentState,
    CommentViewRow,
    ContentState,
)
from src.comments.schemas import CommentCreate, CommentUpdate
from src.comments.service import CommentService
from src.common.exceptions import PermissionDenied
from src.content.enums import ContentStatusEnum, ContentVisibilityEnum, ReactionTypeEnum
from src.users.schemas import UserGet


@dataclass
class FakeContent:
    content_id: uuid.UUID
    author_id: uuid.UUID
    status: ContentStatusEnum
    visibility: ContentVisibilityEnum
    deleted_at: datetime.datetime | None = None
    comments_count: int = 0


@dataclass
class FakeComment:
    comment_id: uuid.UUID
    content_id: uuid.UUID
    author_id: uuid.UUID
    parent_comment_id: uuid.UUID | None
    root_comment_id: uuid.UUID | None
    depth: int
    body_text: str
    created_at: datetime.datetime
    updated_at: datetime.datetime
    deleted_at: datetime.datetime | None = None
    replies_count: int = 0
    likes_count: int = 0
    dislikes_count: int = 0


class FakeCommentRepository:
    def __init__(self, users: dict[uuid.UUID, UserGet]) -> None:
        self.users = users
        self.contents: dict[uuid.UUID, FakeContent] = {}
        self.comments: dict[uuid.UUID, FakeComment] = {}
        self.reactions: dict[tuple[uuid.UUID, uuid.UUID], ReactionTypeEnum] = {}
        self.call_counts: defaultdict[str, int] = defaultdict(int)

    async def get_content_state(
        self,
        *,
        content_id: uuid.UUID,
    ) -> ContentState | None:
        self.call_counts["get_content_state"] += 1
        content = self.contents.get(content_id)
        if content is None:
            return None
        return ContentState(
            content_id=content.content_id,
            author_id=content.author_id,
            status=content.status,
            visibility=content.visibility,
            deleted_at=content.deleted_at,
        )

    async def get_comment_state(
        self,
        *,
        comment_id: uuid.UUID,
    ) -> CommentState | None:
        self.call_counts["get_comment_state"] += 1
        comment = self.comments.get(comment_id)
        if comment is None:
            return None
        return self._to_comment_state(comment)

    async def create_comment(
        self,
        *,
        content_id: uuid.UUID,
        author_id: uuid.UUID,
        parent_comment_id: uuid.UUID | None,
        root_comment_id: uuid.UUID | None,
        depth: int,
        body_text: str,
        created_at: datetime.datetime,
        updated_at: datetime.datetime,
        commit: bool = True,
    ) -> CommentState:
        comment = FakeComment(
            comment_id=uuid.uuid4(),
            content_id=content_id,
            author_id=author_id,
            parent_comment_id=parent_comment_id,
            root_comment_id=root_comment_id,
            depth=depth,
            body_text=body_text,
            created_at=created_at,
            updated_at=updated_at,
        )
        self.comments[comment.comment_id] = comment
        self.contents[content_id].comments_count += 1
        if parent_comment_id is not None:
            self.comments[parent_comment_id].replies_count += 1
        return self._to_comment_state(comment)

    async def update_comment_body(
        self,
        *,
        comment_id: uuid.UUID,
        body_text: str,
        updated_at: datetime.datetime,
        commit: bool = True,
    ) -> None:
        comment = self.comments[comment_id]
        comment.body_text = body_text
        comment.updated_at = updated_at

    async def mark_comment_deleted(
        self,
        *,
        comment_id: uuid.UUID,
        updated_at: datetime.datetime,
        deleted_at: datetime.datetime,
        commit: bool = True,
    ) -> None:
        comment = self.comments[comment_id]
        comment.updated_at = updated_at
        comment.deleted_at = deleted_at

    async def clear_comment_reactions(
        self,
        *,
        comment_id: uuid.UUID,
        commit: bool = True,
    ) -> None:
        keys_to_delete = [
            key
            for key in self.reactions
            if key[0] == comment_id
        ]
        for key in keys_to_delete:
            del self.reactions[key]

        comment = self.comments[comment_id]
        comment.likes_count = 0
        comment.dislikes_count = 0

    async def adjust_content_comments_count(
        self,
        *,
        content_id: uuid.UUID,
        delta: int,
        commit: bool = True,
    ) -> None:
        self.contents[content_id].comments_count += delta

    async def adjust_comment_replies_count(
        self,
        *,
        comment_id: uuid.UUID,
        delta: int,
        commit: bool = True,
    ) -> None:
        self.comments[comment_id].replies_count += delta

    async def get_comment_view(
        self,
        *,
        comment_id: uuid.UUID,
        viewer_id: uuid.UUID | None,
    ) -> CommentViewRow | None:
        self.call_counts["get_comment_view"] += 1
        comment = self.comments.get(comment_id)
        if comment is None:
            return None
        return self._build_comment_view(comment=comment, viewer_id=viewer_id)

    async def list_root_comments(
        self,
        *,
        content_id: uuid.UUID,
        viewer_id: uuid.UUID | None,
        offset: int,
        limit: int,
    ) -> CommentPageResult:
        self.call_counts["list_root_comments"] += 1
        comments = [
            comment for comment in self.comments.values()
            if comment.content_id == content_id
            and comment.parent_comment_id is None
            and self._is_visible(comment)
        ]
        comments.sort(key=lambda comment: comment.created_at, reverse=True)
        page_items = comments[offset: offset + limit]
        return CommentPageResult(
            items=[
                self._build_comment_view(comment=comment, viewer_id=viewer_id)
                for comment in page_items
            ],
            offset=offset,
            limit=limit,
            has_more=offset + limit < len(comments),
        )

    async def list_replies(
        self,
        *,
        parent_comment_id: uuid.UUID,
        viewer_id: uuid.UUID | None,
        offset: int,
        limit: int,
    ) -> CommentPageResult:
        self.call_counts["list_replies"] += 1
        comments = [
            comment for comment in self.comments.values()
            if comment.parent_comment_id == parent_comment_id
            and self._is_visible(comment)
        ]
        comments.sort(key=lambda comment: comment.created_at)
        page_items = comments[offset: offset + limit]
        return CommentPageResult(
            items=[
                self._build_comment_view(comment=comment, viewer_id=viewer_id)
                for comment in page_items
            ],
            offset=offset,
            limit=limit,
            has_more=offset + limit < len(comments),
        )

    async def get_comment_rating(
        self,
        *,
        comment_id: uuid.UUID,
        viewer_id: uuid.UUID | None,
    ) -> CommentRatingRow | None:
        self.call_counts["get_comment_rating"] += 1
        comment = self.comments.get(comment_id)
        if comment is None:
            return None
        return CommentRatingRow(
            comment_id=comment.comment_id,
            likes_count=comment.likes_count,
            dislikes_count=comment.dislikes_count,
            my_reaction=self.reactions.get((comment_id, viewer_id)) if viewer_id else None,
        )

    async def set_reaction(
        self,
        *,
        comment_id: uuid.UUID,
        user_id: uuid.UUID,
        reaction_type: ReactionTypeEnum,
    ) -> None:
        comment = self.comments[comment_id]
        current_reaction = self.reactions.get((comment_id, user_id))

        if current_reaction == reaction_type:
            return

        if current_reaction is None:
            if reaction_type == ReactionTypeEnum.LIKE:
                comment.likes_count += 1
            else:
                comment.dislikes_count += 1
        elif current_reaction == ReactionTypeEnum.LIKE:
            comment.likes_count -= 1
            comment.dislikes_count += 1
        else:
            comment.dislikes_count -= 1
            comment.likes_count += 1

        self.reactions[(comment_id, user_id)] = reaction_type

    async def remove_reaction(
        self,
        *,
        comment_id: uuid.UUID,
        user_id: uuid.UUID,
        reaction_type: ReactionTypeEnum,
    ) -> None:
        current_reaction = self.reactions.get((comment_id, user_id))
        if current_reaction != reaction_type:
            return

        comment = self.comments[comment_id]
        if reaction_type == ReactionTypeEnum.LIKE:
            comment.likes_count -= 1
        else:
            comment.dislikes_count -= 1

        del self.reactions[(comment_id, user_id)]

    async def commit(self) -> None:
        self.call_counts["commit"] += 1
        return None

    def seed_content(
        self,
        *,
        author: UserGet,
        status: ContentStatusEnum = ContentStatusEnum.PUBLISHED,
        visibility: ContentVisibilityEnum = ContentVisibilityEnum.PUBLIC,
        deleted_at: datetime.datetime | None = None,
    ) -> FakeContent:
        content = FakeContent(
            content_id=uuid.uuid4(),
            author_id=author.user_id,
            status=status,
            visibility=visibility,
            deleted_at=deleted_at,
        )
        self.contents[content.content_id] = content
        return content

    def seed_comment(
        self,
        *,
        content_id: uuid.UUID,
        author: UserGet,
        body_text: str,
        created_at: datetime.datetime,
        parent_comment_id: uuid.UUID | None = None,
        deleted_at: datetime.datetime | None = None,
    ) -> FakeComment:
        parent_comment = self.comments.get(parent_comment_id) if parent_comment_id else None
        comment = FakeComment(
            comment_id=uuid.uuid4(),
            content_id=content_id,
            author_id=author.user_id,
            parent_comment_id=parent_comment_id,
            root_comment_id=(
                None
                if parent_comment is None
                else (parent_comment.root_comment_id or parent_comment.comment_id)
            ),
            depth=0 if parent_comment is None else parent_comment.depth + 1,
            body_text=body_text,
            created_at=created_at,
            updated_at=created_at,
            deleted_at=deleted_at,
        )
        self.comments[comment.comment_id] = comment
        self.rebuild_seed_counters()
        return comment

    def seed_reaction(
        self,
        *,
        comment_id: uuid.UUID,
        user_id: uuid.UUID,
        reaction_type: ReactionTypeEnum,
    ) -> None:
        self.reactions[(comment_id, user_id)] = reaction_type
        self._rebuild_reaction_counters()

    def rebuild_seed_counters(self) -> None:
        for content in self.contents.values():
            content.comments_count = 0

        for comment in self.comments.values():
            comment.replies_count = 0

        for depth in sorted({comment.depth for comment in self.comments.values()}, reverse=True):
            for comment in [
                item for item in self.comments.values()
                if item.depth == depth
            ]:
                comment.replies_count = sum(
                    1
                    for child in self.comments.values()
                    if child.parent_comment_id == comment.comment_id
                    and self._is_visible(child)
                )

        for content in self.contents.values():
            content.comments_count = sum(
                1
                for comment in self.comments.values()
                if comment.content_id == content.content_id
                and comment.deleted_at is None
            )

        self._rebuild_reaction_counters()

    def _rebuild_reaction_counters(self) -> None:
        for comment in self.comments.values():
            comment.likes_count = 0
            comment.dislikes_count = 0

        for (comment_id, _user_id), reaction_type in self.reactions.items():
            comment = self.comments.get(comment_id)
            if comment is None:
                continue
            if reaction_type == ReactionTypeEnum.LIKE:
                comment.likes_count += 1
            else:
                comment.dislikes_count += 1

    def _to_comment_state(self, comment: FakeComment) -> CommentState:
        return CommentState(
            comment_id=comment.comment_id,
            content_id=comment.content_id,
            author_id=comment.author_id,
            parent_comment_id=comment.parent_comment_id,
            root_comment_id=comment.root_comment_id,
            depth=comment.depth,
            body_text=comment.body_text,
            replies_count=comment.replies_count,
            likes_count=comment.likes_count,
            dislikes_count=comment.dislikes_count,
            created_at=comment.created_at,
            updated_at=comment.updated_at,
            deleted_at=comment.deleted_at,
        )

    def _build_comment_view(
        self,
        *,
        comment: FakeComment,
        viewer_id: uuid.UUID | None,
    ) -> CommentViewRow:
        parent_comment = self.comments.get(comment.parent_comment_id) if comment.parent_comment_id else None
        author = None
        if comment.deleted_at is None:
            user = self.users[comment.author_id]
            author = CommentAuthorRow(
                user_id=user.user_id,
                username=user.username,
            )

        reply_to_username = None
        if parent_comment is not None and parent_comment.deleted_at is None:
            reply_to_username = self.users[parent_comment.author_id].username

        parent_comment_ref = None
        if parent_comment is not None:
            parent_comment_ref = CommentParentRefRow(
                comment_id=parent_comment.comment_id,
                is_deleted=parent_comment.deleted_at is not None,
            )

        return CommentViewRow(
            comment_id=comment.comment_id,
            content_id=comment.content_id,
            author=author,
            parent_comment_id=comment.parent_comment_id,
            root_comment_id=comment.root_comment_id,
            depth=comment.depth,
            body_text=None if comment.deleted_at is not None else comment.body_text,
            created_at=comment.created_at,
            updated_at=comment.updated_at,
            deleted_at=comment.deleted_at,
            replies_count=comment.replies_count,
            likes_count=comment.likes_count,
            dislikes_count=comment.dislikes_count,
            my_reaction=self.reactions.get((comment.comment_id, viewer_id)) if viewer_id else None,
            is_owner=viewer_id == comment.author_id,
            is_deleted=comment.deleted_at is not None,
            reply_to_username=reply_to_username,
            parent_comment_ref=parent_comment_ref,
        )

    def _is_visible(self, comment: FakeComment) -> bool:
        return comment.deleted_at is None or comment.replies_count > 0


@dataclass
class ServiceBundle:
    service: CommentService
    repository: FakeCommentRepository
    author: UserGet
    stranger: UserGet
    second_user: UserGet


@pytest.fixture
def service_bundle() -> ServiceBundle:
    author = UserGet(
        user_id=uuid.uuid4(),
        username="author",
        is_admin=False,
        subscribers_count=0,
    )
    stranger = UserGet(
        user_id=uuid.uuid4(),
        username="stranger",
        is_admin=False,
        subscribers_count=0,
    )
    second_user = UserGet(
        user_id=uuid.uuid4(),
        username="second",
        is_admin=False,
        subscribers_count=0,
    )
    repository = FakeCommentRepository(
        users={
            author.user_id: author,
            stranger.user_id: stranger,
            second_user.user_id: second_user,
        }
    )
    return ServiceBundle(
        service=CommentService(repository=repository),  # type: ignore[arg-type]
        repository=repository,
        author=author,
        stranger=stranger,
        second_user=second_user,
    )


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def dt(minutes: int) -> datetime.datetime:
    return datetime.datetime(2026, 3, 11, 12, 0, tzinfo=datetime.timezone.utc) + datetime.timedelta(minutes=minutes)


@pytest.mark.anyio
async def test_create_root_comment_for_published_public_content_works(service_bundle: ServiceBundle) -> None:
    content = service_bundle.repository.seed_content(author=service_bundle.author)

    comment = await service_bundle.service.create_root_comment(
        content_id=content.content_id,
        user=service_bundle.stranger,
        data=CommentCreate(body_text="First root comment"),
    )

    stored = service_bundle.repository.comments[comment.comment_id]
    assert comment.parent_comment_id is None
    assert comment.root_comment_id is None
    assert comment.depth == 0
    assert stored.parent_comment_id is None
    assert stored.root_comment_id is None
    assert stored.depth == 0
    assert service_bundle.repository.contents[content.content_id].comments_count == 1


@pytest.mark.anyio
async def test_create_reply_sets_parent_root_and_depth_correctly(service_bundle: ServiceBundle) -> None:
    content = service_bundle.repository.seed_content(author=service_bundle.author)
    root_comment = service_bundle.repository.seed_comment(
        content_id=content.content_id,
        author=service_bundle.author,
        body_text="Root",
        created_at=dt(0),
    )

    reply = await service_bundle.service.create_reply(
        comment_id=root_comment.comment_id,
        user=service_bundle.stranger,
        data=CommentCreate(body_text="Reply"),
    )

    stored = service_bundle.repository.comments[reply.comment_id]
    assert reply.parent_comment_id == root_comment.comment_id
    assert reply.root_comment_id == root_comment.comment_id
    assert reply.depth == 1
    assert stored.parent_comment_id == root_comment.comment_id
    assert stored.root_comment_id == root_comment.comment_id
    assert stored.depth == 1


@pytest.mark.anyio
async def test_deep_reply_is_allowed(service_bundle: ServiceBundle) -> None:
    content = service_bundle.repository.seed_content(author=service_bundle.author)
    parent = service_bundle.repository.seed_comment(
        content_id=content.content_id,
        author=service_bundle.author,
        body_text="depth0",
        created_at=dt(0),
    )
    for minute in range(1, 6):
        parent = service_bundle.repository.seed_comment(
            content_id=content.content_id,
            author=service_bundle.author,
            body_text=f"depth{minute}",
            created_at=dt(minute),
            parent_comment_id=parent.comment_id,
        )

    reply = await service_bundle.service.create_reply(
        comment_id=parent.comment_id,
        user=service_bundle.stranger,
        data=CommentCreate(body_text="still valid"),
    )

    assert reply.parent_comment_id == parent.comment_id
    assert reply.root_comment_id is not None
    assert reply.depth == parent.depth + 1


@pytest.mark.anyio
async def test_empty_comment_is_rejected(service_bundle: ServiceBundle) -> None:
    content = service_bundle.repository.seed_content(author=service_bundle.author)

    with pytest.raises(InvalidComment):
        await service_bundle.service.create_root_comment(
            content_id=content.content_id,
            user=service_bundle.stranger,
            data=CommentCreate(body_text="   "),
        )


@pytest.mark.anyio
async def test_comment_longer_than_2048_is_rejected(service_bundle: ServiceBundle) -> None:
    content = service_bundle.repository.seed_content(author=service_bundle.author)

    with pytest.raises(InvalidComment):
        await service_bundle.service.create_root_comment(
            content_id=content.content_id,
            user=service_bundle.stranger,
            data=CommentCreate.model_construct(body_text="x" * 2049),
        )


@pytest.mark.anyio
async def test_draft_content_does_not_accept_comments(service_bundle: ServiceBundle) -> None:
    content = service_bundle.repository.seed_content(
        author=service_bundle.author,
        status=ContentStatusEnum.DRAFT,
    )

    with pytest.raises(CommentNotFound):
        await service_bundle.service.create_root_comment(
            content_id=content.content_id,
            user=service_bundle.author,
            data=CommentCreate(body_text="draft comment"),
        )


@pytest.mark.anyio
async def test_deleted_content_does_not_accept_comments(service_bundle: ServiceBundle) -> None:
    content = service_bundle.repository.seed_content(
        author=service_bundle.author,
        status=ContentStatusEnum.DELETED,
        deleted_at=dt(0),
    )

    with pytest.raises(CommentNotFound):
        await service_bundle.service.create_root_comment(
            content_id=content.content_id,
            user=service_bundle.author,
            data=CommentCreate(body_text="deleted content comment"),
        )


@pytest.mark.anyio
async def test_private_content_does_not_accept_comments_from_user_without_access(service_bundle: ServiceBundle) -> None:
    content = service_bundle.repository.seed_content(
        author=service_bundle.author,
        visibility=ContentVisibilityEnum.PRIVATE,
    )

    with pytest.raises(CommentNotFound):
        await service_bundle.service.create_root_comment(
            content_id=content.content_id,
            user=service_bundle.stranger,
            data=CommentCreate(body_text="private comment"),
        )


@pytest.mark.anyio
async def test_edit_own_undeleted_comment_works(service_bundle: ServiceBundle) -> None:
    content = service_bundle.repository.seed_content(author=service_bundle.author)
    comment = service_bundle.repository.seed_comment(
        content_id=content.content_id,
        author=service_bundle.stranger,
        body_text="before",
        created_at=dt(0),
    )

    updated = await service_bundle.service.update_comment(
        comment_id=comment.comment_id,
        user=service_bundle.stranger,
        data=CommentUpdate(body_text="after"),
    )

    assert updated.body_text == "after"
    assert service_bundle.repository.comments[comment.comment_id].body_text == "after"
    assert updated.updated_at > updated.created_at


@pytest.mark.anyio
async def test_edit_foreign_comment_is_forbidden(service_bundle: ServiceBundle) -> None:
    content = service_bundle.repository.seed_content(author=service_bundle.author)
    comment = service_bundle.repository.seed_comment(
        content_id=content.content_id,
        author=service_bundle.author,
        body_text="foreign",
        created_at=dt(0),
    )

    with pytest.raises(PermissionDenied):
        await service_bundle.service.update_comment(
            comment_id=comment.comment_id,
            user=service_bundle.stranger,
            data=CommentUpdate(body_text="nope"),
        )


@pytest.mark.anyio
async def test_edit_deleted_comment_is_forbidden(service_bundle: ServiceBundle) -> None:
    content = service_bundle.repository.seed_content(author=service_bundle.author)
    comment = service_bundle.repository.seed_comment(
        content_id=content.content_id,
        author=service_bundle.stranger,
        body_text="deleted",
        created_at=dt(0),
        deleted_at=dt(1),
    )

    with pytest.raises(InvalidComment):
        await service_bundle.service.update_comment(
            comment_id=comment.comment_id,
            user=service_bundle.stranger,
            data=CommentUpdate(body_text="edited"),
        )


@pytest.mark.anyio
async def test_comment_with_replies_can_still_be_edited(service_bundle: ServiceBundle) -> None:
    content = service_bundle.repository.seed_content(author=service_bundle.author)
    comment = service_bundle.repository.seed_comment(
        content_id=content.content_id,
        author=service_bundle.stranger,
        body_text="parent",
        created_at=dt(0),
    )
    service_bundle.repository.seed_comment(
        content_id=content.content_id,
        author=service_bundle.second_user,
        body_text="reply",
        created_at=dt(1),
        parent_comment_id=comment.comment_id,
    )

    updated = await service_bundle.service.update_comment(
        comment_id=comment.comment_id,
        user=service_bundle.stranger,
        data=CommentUpdate(body_text="edited parent"),
    )

    assert updated.body_text == "edited parent"
    assert service_bundle.repository.comments[comment.comment_id].replies_count == 1


@pytest.mark.anyio
async def test_soft_delete_comment_without_replies_hides_it_from_regular_listing(service_bundle: ServiceBundle) -> None:
    content = service_bundle.repository.seed_content(author=service_bundle.author)
    comment = service_bundle.repository.seed_comment(
        content_id=content.content_id,
        author=service_bundle.stranger,
        body_text="hide me",
        created_at=dt(0),
    )

    await service_bundle.service.delete_comment(
        comment_id=comment.comment_id,
        user=service_bundle.stranger,
    )

    page = await service_bundle.service.get_root_comments(
        content_id=content.content_id,
        offset=0,
        limit=20,
        user=service_bundle.author,
    )

    assert page.items == []
    assert service_bundle.repository.contents[content.content_id].comments_count == 0


@pytest.mark.anyio
async def test_soft_delete_comment_with_replies_leaves_tombstone(service_bundle: ServiceBundle) -> None:
    content = service_bundle.repository.seed_content(author=service_bundle.author)
    comment = service_bundle.repository.seed_comment(
        content_id=content.content_id,
        author=service_bundle.stranger,
        body_text="tombstone me",
        created_at=dt(0),
    )
    service_bundle.repository.seed_comment(
        content_id=content.content_id,
        author=service_bundle.second_user,
        body_text="keep thread alive",
        created_at=dt(1),
        parent_comment_id=comment.comment_id,
    )

    await service_bundle.service.delete_comment(
        comment_id=comment.comment_id,
        user=service_bundle.stranger,
    )

    page = await service_bundle.service.get_root_comments(
        content_id=content.content_id,
        offset=0,
        limit=20,
        user=service_bundle.author,
    )

    assert len(page.items) == 1
    tombstone = page.items[0]
    assert tombstone.is_deleted is True
    assert tombstone.author is None
    assert tombstone.body_text is None
    assert tombstone.replies_count == 1
    assert service_bundle.repository.contents[content.content_id].comments_count == 1


@pytest.mark.anyio
async def test_root_comments_are_sorted_by_created_at_desc(service_bundle: ServiceBundle) -> None:
    content = service_bundle.repository.seed_content(author=service_bundle.author)
    first = service_bundle.repository.seed_comment(
        content_id=content.content_id,
        author=service_bundle.author,
        body_text="older",
        created_at=dt(0),
    )
    second = service_bundle.repository.seed_comment(
        content_id=content.content_id,
        author=service_bundle.stranger,
        body_text="newer",
        created_at=dt(1),
    )

    page = await service_bundle.service.get_root_comments(
        content_id=content.content_id,
        offset=0,
        limit=20,
        user=service_bundle.author,
    )

    assert [item.comment_id for item in page.items] == [second.comment_id, first.comment_id]


@pytest.mark.anyio
async def test_replies_are_sorted_by_created_at_asc(service_bundle: ServiceBundle) -> None:
    content = service_bundle.repository.seed_content(author=service_bundle.author)
    root = service_bundle.repository.seed_comment(
        content_id=content.content_id,
        author=service_bundle.author,
        body_text="root",
        created_at=dt(0),
    )
    first = service_bundle.repository.seed_comment(
        content_id=content.content_id,
        author=service_bundle.stranger,
        body_text="first",
        created_at=dt(2),
        parent_comment_id=root.comment_id,
    )
    second = service_bundle.repository.seed_comment(
        content_id=content.content_id,
        author=service_bundle.second_user,
        body_text="second",
        created_at=dt(1),
        parent_comment_id=root.comment_id,
    )

    page = await service_bundle.service.get_replies(
        comment_id=root.comment_id,
        offset=0,
        limit=20,
        user=service_bundle.author,
    )

    assert [item.comment_id for item in page.items] == [second.comment_id, first.comment_id]


@pytest.mark.anyio
async def test_replies_count_updates_correctly(service_bundle: ServiceBundle) -> None:
    content = service_bundle.repository.seed_content(author=service_bundle.author)
    root = service_bundle.repository.seed_comment(
        content_id=content.content_id,
        author=service_bundle.author,
        body_text="root",
        created_at=dt(0),
    )

    reply = await service_bundle.service.create_reply(
        comment_id=root.comment_id,
        user=service_bundle.stranger,
        data=CommentCreate(body_text="reply"),
    )
    assert service_bundle.repository.comments[root.comment_id].replies_count == 1

    await service_bundle.service.delete_comment(
        comment_id=reply.comment_id,
        user=service_bundle.stranger,
    )
    assert service_bundle.repository.comments[root.comment_id].replies_count == 0


@pytest.mark.anyio
async def test_content_comments_count_updates_correctly(service_bundle: ServiceBundle) -> None:
    content = service_bundle.repository.seed_content(author=service_bundle.author)
    root = await service_bundle.service.create_root_comment(
        content_id=content.content_id,
        user=service_bundle.stranger,
        data=CommentCreate(body_text="root"),
    )
    reply = await service_bundle.service.create_reply(
        comment_id=root.comment_id,
        user=service_bundle.second_user,
        data=CommentCreate(body_text="reply"),
    )

    assert service_bundle.repository.contents[content.content_id].comments_count == 2

    await service_bundle.service.delete_comment(
        comment_id=root.comment_id,
        user=service_bundle.stranger,
    )
    assert service_bundle.repository.contents[content.content_id].comments_count == 1

    await service_bundle.service.delete_comment(
        comment_id=reply.comment_id,
        user=service_bundle.second_user,
    )
    assert service_bundle.repository.contents[content.content_id].comments_count == 0


@pytest.mark.anyio
async def test_like_from_neutral_on_comment_works(service_bundle: ServiceBundle) -> None:
    content = service_bundle.repository.seed_content(author=service_bundle.author)
    comment = service_bundle.repository.seed_comment(
        content_id=content.content_id,
        author=service_bundle.author,
        body_text="comment",
        created_at=dt(0),
    )

    rating = await service_bundle.service.add_like(
        comment_id=comment.comment_id,
        user_id=service_bundle.stranger.user_id,
    )

    assert rating.likes_count == 1
    assert rating.dislikes_count == 0
    assert rating.my_reaction == ReactionTypeEnum.LIKE


@pytest.mark.anyio
async def test_dislike_from_neutral_on_comment_works(service_bundle: ServiceBundle) -> None:
    content = service_bundle.repository.seed_content(author=service_bundle.author)
    comment = service_bundle.repository.seed_comment(
        content_id=content.content_id,
        author=service_bundle.author,
        body_text="comment",
        created_at=dt(0),
    )

    rating = await service_bundle.service.add_dislike(
        comment_id=comment.comment_id,
        user_id=service_bundle.stranger.user_id,
    )

    assert rating.likes_count == 0
    assert rating.dislikes_count == 1
    assert rating.my_reaction == ReactionTypeEnum.DISLIKE


@pytest.mark.anyio
async def test_switch_dislike_to_like_on_comment_works(service_bundle: ServiceBundle) -> None:
    content = service_bundle.repository.seed_content(author=service_bundle.author)
    comment = service_bundle.repository.seed_comment(
        content_id=content.content_id,
        author=service_bundle.author,
        body_text="comment",
        created_at=dt(0),
    )
    service_bundle.repository.seed_reaction(
        comment_id=comment.comment_id,
        user_id=service_bundle.stranger.user_id,
        reaction_type=ReactionTypeEnum.DISLIKE,
    )

    rating = await service_bundle.service.add_like(
        comment_id=comment.comment_id,
        user_id=service_bundle.stranger.user_id,
    )

    assert rating.likes_count == 1
    assert rating.dislikes_count == 0
    assert rating.my_reaction == ReactionTypeEnum.LIKE


@pytest.mark.anyio
async def test_switch_like_to_dislike_on_comment_works(service_bundle: ServiceBundle) -> None:
    content = service_bundle.repository.seed_content(author=service_bundle.author)
    comment = service_bundle.repository.seed_comment(
        content_id=content.content_id,
        author=service_bundle.author,
        body_text="comment",
        created_at=dt(0),
    )
    service_bundle.repository.seed_reaction(
        comment_id=comment.comment_id,
        user_id=service_bundle.stranger.user_id,
        reaction_type=ReactionTypeEnum.LIKE,
    )

    rating = await service_bundle.service.add_dislike(
        comment_id=comment.comment_id,
        user_id=service_bundle.stranger.user_id,
    )

    assert rating.likes_count == 0
    assert rating.dislikes_count == 1
    assert rating.my_reaction == ReactionTypeEnum.DISLIKE


@pytest.mark.anyio
async def test_remove_like_on_comment_works(service_bundle: ServiceBundle) -> None:
    content = service_bundle.repository.seed_content(author=service_bundle.author)
    comment = service_bundle.repository.seed_comment(
        content_id=content.content_id,
        author=service_bundle.author,
        body_text="comment",
        created_at=dt(0),
    )
    service_bundle.repository.seed_reaction(
        comment_id=comment.comment_id,
        user_id=service_bundle.stranger.user_id,
        reaction_type=ReactionTypeEnum.LIKE,
    )

    rating = await service_bundle.service.remove_like(
        comment_id=comment.comment_id,
        user_id=service_bundle.stranger.user_id,
    )

    assert rating.likes_count == 0
    assert rating.dislikes_count == 0
    assert rating.my_reaction is None


@pytest.mark.anyio
async def test_remove_dislike_on_comment_works(service_bundle: ServiceBundle) -> None:
    content = service_bundle.repository.seed_content(author=service_bundle.author)
    comment = service_bundle.repository.seed_comment(
        content_id=content.content_id,
        author=service_bundle.author,
        body_text="comment",
        created_at=dt(0),
    )
    service_bundle.repository.seed_reaction(
        comment_id=comment.comment_id,
        user_id=service_bundle.stranger.user_id,
        reaction_type=ReactionTypeEnum.DISLIKE,
    )

    rating = await service_bundle.service.remove_dislike(
        comment_id=comment.comment_id,
        user_id=service_bundle.stranger.user_id,
    )

    assert rating.likes_count == 0
    assert rating.dislikes_count == 0
    assert rating.my_reaction is None


@pytest.mark.anyio
async def test_cannot_react_to_deleted_comment(service_bundle: ServiceBundle) -> None:
    content = service_bundle.repository.seed_content(author=service_bundle.author)
    comment = service_bundle.repository.seed_comment(
        content_id=content.content_id,
        author=service_bundle.author,
        body_text="comment",
        created_at=dt(0),
        deleted_at=dt(1),
    )

    with pytest.raises(CommentNotFound):
        await service_bundle.service.add_like(
            comment_id=comment.comment_id,
            user_id=service_bundle.stranger.user_id,
        )


@pytest.mark.anyio
async def test_cannot_react_to_comment_of_inaccessible_content(service_bundle: ServiceBundle) -> None:
    content = service_bundle.repository.seed_content(
        author=service_bundle.author,
        visibility=ContentVisibilityEnum.PRIVATE,
    )
    comment = service_bundle.repository.seed_comment(
        content_id=content.content_id,
        author=service_bundle.author,
        body_text="comment",
        created_at=dt(0),
    )

    with pytest.raises(CommentNotFound):
        await service_bundle.service.add_like(
            comment_id=comment.comment_id,
            user_id=service_bundle.stranger.user_id,
        )


@pytest.mark.anyio
async def test_get_root_comments_returns_my_reaction_correctly(service_bundle: ServiceBundle) -> None:
    content = service_bundle.repository.seed_content(author=service_bundle.author)
    liked = service_bundle.repository.seed_comment(
        content_id=content.content_id,
        author=service_bundle.author,
        body_text="liked",
        created_at=dt(0),
    )
    service_bundle.repository.seed_reaction(
        comment_id=liked.comment_id,
        user_id=service_bundle.stranger.user_id,
        reaction_type=ReactionTypeEnum.LIKE,
    )

    page = await service_bundle.service.get_root_comments(
        content_id=content.content_id,
        offset=0,
        limit=20,
        user=service_bundle.stranger,
    )

    assert page.items[0].my_reaction == ReactionTypeEnum.LIKE


@pytest.mark.anyio
async def test_get_replies_returns_my_reaction_correctly(service_bundle: ServiceBundle) -> None:
    content = service_bundle.repository.seed_content(author=service_bundle.author)
    root = service_bundle.repository.seed_comment(
        content_id=content.content_id,
        author=service_bundle.author,
        body_text="root",
        created_at=dt(0),
    )
    reply = service_bundle.repository.seed_comment(
        content_id=content.content_id,
        author=service_bundle.second_user,
        body_text="reply",
        created_at=dt(1),
        parent_comment_id=root.comment_id,
    )
    service_bundle.repository.seed_reaction(
        comment_id=reply.comment_id,
        user_id=service_bundle.stranger.user_id,
        reaction_type=ReactionTypeEnum.DISLIKE,
    )

    page = await service_bundle.service.get_replies(
        comment_id=root.comment_id,
        offset=0,
        limit=20,
        user=service_bundle.stranger,
    )

    assert page.items[0].my_reaction == ReactionTypeEnum.DISLIKE


@pytest.mark.anyio
async def test_comment_listing_does_not_trigger_service_level_n_plus_one_for_root_comments(service_bundle: ServiceBundle) -> None:
    content = service_bundle.repository.seed_content(author=service_bundle.author)
    first = service_bundle.repository.seed_comment(
        content_id=content.content_id,
        author=service_bundle.author,
        body_text="first",
        created_at=dt(0),
    )
    second = service_bundle.repository.seed_comment(
        content_id=content.content_id,
        author=service_bundle.second_user,
        body_text="second",
        created_at=dt(1),
    )
    service_bundle.repository.seed_reaction(
        comment_id=second.comment_id,
        user_id=service_bundle.stranger.user_id,
        reaction_type=ReactionTypeEnum.LIKE,
    )

    page = await service_bundle.service.get_root_comments(
        content_id=content.content_id,
        offset=0,
        limit=20,
        user=service_bundle.stranger,
    )

    assert {item.comment_id for item in page.items} == {first.comment_id, second.comment_id}
    assert service_bundle.repository.call_counts["get_content_state"] == 1
    assert service_bundle.repository.call_counts["list_root_comments"] == 1
    assert service_bundle.repository.call_counts["get_comment_state"] == 0
    assert service_bundle.repository.call_counts["get_comment_view"] == 0
    assert service_bundle.repository.call_counts["get_comment_rating"] == 0


@pytest.mark.anyio
async def test_comment_listing_does_not_trigger_service_level_n_plus_one_for_replies(service_bundle: ServiceBundle) -> None:
    content = service_bundle.repository.seed_content(author=service_bundle.author)
    root = service_bundle.repository.seed_comment(
        content_id=content.content_id,
        author=service_bundle.author,
        body_text="root",
        created_at=dt(0),
    )
    service_bundle.repository.seed_comment(
        content_id=content.content_id,
        author=service_bundle.stranger,
        body_text="reply one",
        created_at=dt(1),
        parent_comment_id=root.comment_id,
    )
    service_bundle.repository.seed_comment(
        content_id=content.content_id,
        author=service_bundle.second_user,
        body_text="reply two",
        created_at=dt(2),
        parent_comment_id=root.comment_id,
    )

    page = await service_bundle.service.get_replies(
        comment_id=root.comment_id,
        offset=0,
        limit=20,
        user=service_bundle.author,
    )

    assert len(page.items) == 2
    assert service_bundle.repository.call_counts["get_comment_state"] == 1
    assert service_bundle.repository.call_counts["get_content_state"] == 1
    assert service_bundle.repository.call_counts["list_replies"] == 1
    assert service_bundle.repository.call_counts["get_comment_view"] == 0
    assert service_bundle.repository.call_counts["get_comment_rating"] == 0
