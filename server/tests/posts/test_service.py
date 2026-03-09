import datetime
import uuid
from dataclasses import dataclass

import pytest

from src.content.enums import ContentStatusEnum, ContentVisibilityEnum, ReactionTypeEnum
from src.posts.enums import PostOrder, PostProfileFilter
from src.posts.exceptions import PostNotFound
from src.posts.schemas import PostCreate, PostUpdate
from src.posts.service import PostService
from src.users.schemas import UserGet


@dataclass
class FakePostDetails:
    body_text: str


@dataclass
class FakePost:
    content_id: uuid.UUID
    author_id: uuid.UUID
    author: UserGet
    post_details: FakePostDetails
    status: ContentStatusEnum
    visibility: ContentVisibilityEnum
    created_at: datetime.datetime
    updated_at: datetime.datetime
    published_at: datetime.datetime | None = None
    deleted_at: datetime.datetime | None = None
    likes_count: int = 0
    dislikes_count: int = 0
    my_reaction: ReactionTypeEnum | None = None
    is_owner: bool = False

    @property
    def post_id(self) -> uuid.UUID:
        return self.content_id

    @property
    def user_id(self) -> uuid.UUID:
        return self.author_id

    @property
    def user(self) -> UserGet:
        return self.author

    @property
    def content(self) -> str:
        return self.post_details.body_text


class FakePostRepository:
    def __init__(self, users: dict[uuid.UUID, UserGet]) -> None:
        self.users = users
        self.posts: dict[uuid.UUID, FakePost] = {}
        self.reactions: dict[tuple[uuid.UUID, uuid.UUID], ReactionTypeEnum] = {}
        self.subscriptions: set[tuple[uuid.UUID, uuid.UUID]] = set()

    async def create(
        self,
        *,
        author_id: uuid.UUID,
        body_text: str,
        status: ContentStatusEnum,
        visibility: ContentVisibilityEnum,
        created_at: datetime.datetime,
        updated_at: datetime.datetime,
        published_at: datetime.datetime | None,
    ) -> FakePost:
        post = FakePost(
            content_id=uuid.uuid4(),
            author_id=author_id,
            author=self.users[author_id],
            post_details=FakePostDetails(body_text=body_text),
            status=status,
            visibility=visibility,
            created_at=created_at,
            updated_at=updated_at,
            published_at=published_at,
        )
        self.posts[post.content_id] = post
        return self._decorate(post, viewer_id=author_id)

    async def get_single(
        self,
        *,
        content_id: uuid.UUID,
        viewer_id: uuid.UUID | None = None,
    ) -> FakePost | None:
        post = self.posts.get(content_id)
        if post is None:
            return None
        return self._decorate(post, viewer_id=viewer_id)

    async def get_feed(
        self,
        *,
        viewer_id: uuid.UUID | None,
        order: PostOrder,
        order_desc: bool,
        offset: int,
        limit: int,
    ) -> list[FakePost]:
        posts = [
            post for post in self.posts.values()
            if post.status == ContentStatusEnum.PUBLISHED
            and post.visibility == ContentVisibilityEnum.PUBLIC
            and post.deleted_at is None
        ]
        return self._decorate_many(
            posts=posts,
            viewer_id=viewer_id,
            order=order,
            order_desc=order_desc,
            offset=offset,
            limit=limit,
        )

    async def get_author_posts(
        self,
        *,
        author_id: uuid.UUID,
        viewer_id: uuid.UUID | None,
        profile_filter: PostProfileFilter,
        order: PostOrder,
        order_desc: bool,
        offset: int,
        limit: int,
    ) -> list[FakePost]:
        posts = [
            post for post in self.posts.values()
            if post.author_id == author_id and post.deleted_at is None
        ]

        if viewer_id == author_id:
            if profile_filter == PostProfileFilter.ALL:
                posts = [
                    post for post in posts
                    if post.status in {ContentStatusEnum.PUBLISHED, ContentStatusEnum.DRAFT}
                ]
            elif profile_filter == PostProfileFilter.DRAFTS:
                posts = [post for post in posts if post.status == ContentStatusEnum.DRAFT]
            elif profile_filter == PostProfileFilter.PRIVATE:
                posts = [
                    post for post in posts
                    if post.status == ContentStatusEnum.PUBLISHED
                    and post.visibility == ContentVisibilityEnum.PRIVATE
                ]
            else:
                posts = [
                    post for post in posts
                    if post.status == ContentStatusEnum.PUBLISHED
                    and post.visibility == ContentVisibilityEnum.PUBLIC
                ]
        else:
            posts = [
                post for post in posts
                if post.status == ContentStatusEnum.PUBLISHED
                and post.visibility == ContentVisibilityEnum.PUBLIC
            ]

        return self._decorate_many(
            posts=posts,
            viewer_id=viewer_id,
            order=order,
            order_desc=order_desc,
            offset=offset,
            limit=limit,
        )

    async def get_user_subscriptions_posts(
        self,
        *,
        user_id: uuid.UUID,
        order: PostOrder,
        order_desc: bool,
        offset: int,
        limit: int,
    ) -> list[FakePost]:
        subscribed_ids = {
            subscribed_id
            for subscriber_id, subscribed_id in self.subscriptions
            if subscriber_id == user_id
        }
        posts = [
            post for post in self.posts.values()
            if post.author_id in subscribed_ids
            and post.status == ContentStatusEnum.PUBLISHED
            and post.visibility == ContentVisibilityEnum.PUBLIC
            and post.deleted_at is None
        ]
        return self._decorate_many(
            posts=posts,
            viewer_id=user_id,
            order=order,
            order_desc=order_desc,
            offset=offset,
            limit=limit,
        )

    async def update_post(
        self,
        *,
        content_id: uuid.UUID,
        body_text: str,
        status: ContentStatusEnum,
        visibility: ContentVisibilityEnum,
        updated_at: datetime.datetime,
        published_at: datetime.datetime | None,
    ) -> FakePost:
        post = self.posts[content_id]
        post.post_details.body_text = body_text
        post.status = status
        post.visibility = visibility
        post.updated_at = updated_at
        post.published_at = published_at
        return self._decorate(post, viewer_id=post.author_id)

    async def soft_delete_post(
        self,
        *,
        content_id: uuid.UUID,
        updated_at: datetime.datetime,
        deleted_at: datetime.datetime,
    ) -> FakePost:
        post = self.posts[content_id]
        post.status = ContentStatusEnum.DELETED
        post.updated_at = updated_at
        post.deleted_at = deleted_at
        return self._decorate(post, viewer_id=post.author_id)

    async def set_reaction(
        self,
        *,
        content_id: uuid.UUID,
        user_id: uuid.UUID,
        reaction_type: ReactionTypeEnum,
    ) -> None:
        post = self.posts[content_id]
        current = self.reactions.get((content_id, user_id))
        if current == reaction_type:
            return

        if current is None:
            if reaction_type == ReactionTypeEnum.LIKE:
                post.likes_count += 1
            else:
                post.dislikes_count += 1
        elif current == ReactionTypeEnum.LIKE:
            post.likes_count -= 1
            post.dislikes_count += 1
        else:
            post.dislikes_count -= 1
            post.likes_count += 1

        self.reactions[(content_id, user_id)] = reaction_type

    async def remove_reaction(
        self,
        *,
        content_id: uuid.UUID,
        user_id: uuid.UUID,
        reaction_type: ReactionTypeEnum,
    ) -> None:
        current = self.reactions.get((content_id, user_id))
        if current != reaction_type:
            return

        post = self.posts[content_id]
        if reaction_type == ReactionTypeEnum.LIKE:
            post.likes_count -= 1
        else:
            post.dislikes_count -= 1

        del self.reactions[(content_id, user_id)]

    def seed_post(
        self,
        *,
        author: UserGet,
        content: str,
        status: ContentStatusEnum,
        visibility: ContentVisibilityEnum,
        created_at: datetime.datetime,
        published_at: datetime.datetime | None = None,
        deleted_at: datetime.datetime | None = None,
    ) -> FakePost:
        post = FakePost(
            content_id=uuid.uuid4(),
            author_id=author.user_id,
            author=author,
            post_details=FakePostDetails(body_text=content),
            status=status,
            visibility=visibility,
            created_at=created_at,
            updated_at=created_at,
            published_at=published_at,
            deleted_at=deleted_at,
        )
        self.posts[post.content_id] = post
        return post

    def _decorate_many(
        self,
        *,
        posts: list[FakePost],
        viewer_id: uuid.UUID | None,
        order: PostOrder,
        order_desc: bool,
        offset: int,
        limit: int,
    ) -> list[FakePost]:
        order_attr = {
            PostOrder.ID: "content_id",
            PostOrder.CREATED_AT: "created_at",
            PostOrder.UPDATED_AT: "updated_at",
            PostOrder.PUBLISHED_AT: "published_at",
        }[order]
        ordered_posts = sorted(
            posts,
            key=lambda post: (getattr(post, order_attr) is None, getattr(post, order_attr)),
            reverse=order_desc,
        )
        return [
            self._decorate(post, viewer_id=viewer_id)
            for post in ordered_posts[offset: offset + limit]
        ]

    def _decorate(self, post: FakePost, viewer_id: uuid.UUID | None) -> FakePost:
        post.is_owner = viewer_id == post.author_id
        post.my_reaction = self.reactions.get((post.content_id, viewer_id)) if viewer_id else None
        return post


@dataclass
class ServiceBundle:
    service: PostService
    repository: FakePostRepository
    author: UserGet
    stranger: UserGet
    follower: UserGet


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
    follower = UserGet(
        user_id=uuid.uuid4(),
        username="follower",
        is_admin=False,
        subscribers_count=0,
    )
    repository = FakePostRepository(
        users={
            author.user_id: author,
            stranger.user_id: stranger,
            follower.user_id: follower,
        }
    )
    repository.subscriptions.add((follower.user_id, author.user_id))
    return ServiceBundle(
        service=PostService(repository=repository),
        repository=repository,
        author=author,
        stranger=stranger,
        follower=follower,
    )


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def dt(minutes: int) -> datetime.datetime:
    return datetime.datetime(2026, 3, 9, 12, 0, tzinfo=datetime.timezone.utc) + datetime.timedelta(minutes=minutes)


@pytest.mark.anyio
async def test_create_post_creates_content_and_post_details(service_bundle: ServiceBundle) -> None:
    post = await service_bundle.service.create_post(
        service_bundle.author,
        PostCreate(content="public body"),
    )

    stored = service_bundle.repository.posts[post.post_id]
    assert post.user_id == service_bundle.author.user_id
    assert post.content == "public body"
    assert post.status == ContentStatusEnum.PUBLISHED
    assert post.visibility == ContentVisibilityEnum.PUBLIC
    assert stored.post_details.body_text == "public body"


@pytest.mark.anyio
async def test_create_private_post_creates_published_private_post(service_bundle: ServiceBundle) -> None:
    post = await service_bundle.service.create_post(
        service_bundle.author,
        PostCreate(content="private body", visibility="private"),
    )

    assert post.status == ContentStatusEnum.PUBLISHED
    assert post.visibility == ContentVisibilityEnum.PRIVATE
    assert post.published_at is not None


@pytest.mark.anyio
async def test_create_draft_post_creates_draft_post(service_bundle: ServiceBundle) -> None:
    post = await service_bundle.service.create_post(
        service_bundle.author,
        PostCreate(content="draft body", status="draft"),
    )

    assert post.status == ContentStatusEnum.DRAFT
    assert post.published_at is None


@pytest.mark.anyio
async def test_get_post_returns_public_published_post(service_bundle: ServiceBundle) -> None:
    post = service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="public post",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(0),
        published_at=dt(0),
    )

    result = await service_bundle.service.get_post(post.content_id, user=service_bundle.stranger)

    assert result.post_id == post.content_id
    assert result.content == "public post"


@pytest.mark.anyio
async def test_get_post_returns_private_post_to_author(service_bundle: ServiceBundle) -> None:
    post = service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="private post",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PRIVATE,
        created_at=dt(1),
        published_at=dt(1),
    )

    result = await service_bundle.service.get_post(post.content_id, user=service_bundle.author)

    assert result.post_id == post.content_id
    assert result.is_owner is True


@pytest.mark.anyio
async def test_get_post_does_not_return_private_post_to_stranger(service_bundle: ServiceBundle) -> None:
    post = service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="private post",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PRIVATE,
        created_at=dt(2),
        published_at=dt(2),
    )

    with pytest.raises(PostNotFound):
        await service_bundle.service.get_post(post.content_id, user=service_bundle.stranger)


@pytest.mark.anyio
async def test_get_post_returns_draft_post_to_author(service_bundle: ServiceBundle) -> None:
    post = service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="draft post",
        status=ContentStatusEnum.DRAFT,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(3),
    )

    result = await service_bundle.service.get_post(post.content_id, user=service_bundle.author)

    assert result.post_id == post.content_id
    assert result.status == ContentStatusEnum.DRAFT


@pytest.mark.anyio
async def test_get_post_does_not_return_draft_post_to_stranger(service_bundle: ServiceBundle) -> None:
    post = service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="draft post",
        status=ContentStatusEnum.DRAFT,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(4),
    )

    with pytest.raises(PostNotFound):
        await service_bundle.service.get_post(post.content_id, user=service_bundle.stranger)


@pytest.mark.anyio
async def test_update_post_updates_body_text_and_updated_at(service_bundle: ServiceBundle) -> None:
    post = service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="before",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(5),
        published_at=dt(5),
    )
    old_updated_at = post.updated_at

    updated = await service_bundle.service.update_post(
        service_bundle.author,
        post.content_id,
        PostUpdate(content="after"),
    )

    assert updated.content == "after"
    assert updated.updated_at > old_updated_at


@pytest.mark.anyio
async def test_update_post_on_deleted_post_is_forbidden(service_bundle: ServiceBundle) -> None:
    post = service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="deleted",
        status=ContentStatusEnum.DELETED,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(6),
        deleted_at=dt(7),
    )

    with pytest.raises(PostNotFound):
        await service_bundle.service.update_post(
            service_bundle.author,
            post.content_id,
            PostUpdate(content="after"),
        )


@pytest.mark.anyio
async def test_publish_draft_sets_published_at(service_bundle: ServiceBundle) -> None:
    post = service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="draft",
        status=ContentStatusEnum.DRAFT,
        visibility=ContentVisibilityEnum.PRIVATE,
        created_at=dt(8),
    )

    updated = await service_bundle.service.update_post(
        service_bundle.author,
        post.content_id,
        PostUpdate(status="published"),
    )

    assert updated.status == ContentStatusEnum.PUBLISHED
    assert updated.published_at is not None


@pytest.mark.anyio
async def test_delete_post_soft_deletes_post(service_bundle: ServiceBundle) -> None:
    post = service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="delete me",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(9),
        published_at=dt(9),
    )

    await service_bundle.service.delete_post(service_bundle.author, post.content_id)

    stored = service_bundle.repository.posts[post.content_id]
    assert stored.status == ContentStatusEnum.DELETED
    assert stored.deleted_at is not None


@pytest.mark.anyio
async def test_delete_post_repeated_is_predictable(service_bundle: ServiceBundle) -> None:
    post = service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="delete me",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(10),
        published_at=dt(10),
    )

    await service_bundle.service.delete_post(service_bundle.author, post.content_id)
    deleted_at = service_bundle.repository.posts[post.content_id].deleted_at
    await service_bundle.service.delete_post(service_bundle.author, post.content_id)

    assert service_bundle.repository.posts[post.content_id].deleted_at == deleted_at


@pytest.mark.anyio
async def test_like_from_neutral(service_bundle: ServiceBundle) -> None:
    post = service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="react",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(11),
        published_at=dt(11),
    )

    rating = await service_bundle.service.add_like_to_post(post.content_id, service_bundle.stranger.user_id)

    assert rating.likes_count == 1
    assert rating.dislikes_count == 0
    assert rating.my_reaction == ReactionTypeEnum.LIKE


@pytest.mark.anyio
async def test_dislike_from_neutral(service_bundle: ServiceBundle) -> None:
    post = service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="react",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(12),
        published_at=dt(12),
    )

    rating = await service_bundle.service.add_dislike_to_post(post.content_id, service_bundle.stranger.user_id)

    assert rating.likes_count == 0
    assert rating.dislikes_count == 1
    assert rating.my_reaction == ReactionTypeEnum.DISLIKE


@pytest.mark.anyio
async def test_switch_dislike_to_like(service_bundle: ServiceBundle) -> None:
    post = service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="react",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(13),
        published_at=dt(13),
    )
    await service_bundle.service.add_dislike_to_post(post.content_id, service_bundle.stranger.user_id)

    rating = await service_bundle.service.add_like_to_post(post.content_id, service_bundle.stranger.user_id)

    assert rating.likes_count == 1
    assert rating.dislikes_count == 0
    assert rating.my_reaction == ReactionTypeEnum.LIKE


@pytest.mark.anyio
async def test_switch_like_to_dislike(service_bundle: ServiceBundle) -> None:
    post = service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="react",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(14),
        published_at=dt(14),
    )
    await service_bundle.service.add_like_to_post(post.content_id, service_bundle.stranger.user_id)

    rating = await service_bundle.service.add_dislike_to_post(post.content_id, service_bundle.stranger.user_id)

    assert rating.likes_count == 0
    assert rating.dislikes_count == 1
    assert rating.my_reaction == ReactionTypeEnum.DISLIKE


@pytest.mark.anyio
async def test_remove_like(service_bundle: ServiceBundle) -> None:
    post = service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="react",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(15),
        published_at=dt(15),
    )
    await service_bundle.service.add_like_to_post(post.content_id, service_bundle.stranger.user_id)

    rating = await service_bundle.service.remove_like_from_post(post.content_id, service_bundle.stranger.user_id)

    assert rating.likes_count == 0
    assert rating.my_reaction is None


@pytest.mark.anyio
async def test_remove_dislike(service_bundle: ServiceBundle) -> None:
    post = service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="react",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(16),
        published_at=dt(16),
    )
    await service_bundle.service.add_dislike_to_post(post.content_id, service_bundle.stranger.user_id)

    rating = await service_bundle.service.remove_dislike_from_post(post.content_id, service_bundle.stranger.user_id)

    assert rating.dislikes_count == 0
    assert rating.my_reaction is None


@pytest.mark.anyio
async def test_repeat_like_is_idempotent(service_bundle: ServiceBundle) -> None:
    post = service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="react",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(17),
        published_at=dt(17),
    )
    await service_bundle.service.add_like_to_post(post.content_id, service_bundle.stranger.user_id)

    rating = await service_bundle.service.add_like_to_post(post.content_id, service_bundle.stranger.user_id)

    assert rating.likes_count == 1
    assert rating.dislikes_count == 0


@pytest.mark.anyio
async def test_repeat_dislike_is_idempotent(service_bundle: ServiceBundle) -> None:
    post = service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="react",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(18),
        published_at=dt(18),
    )
    await service_bundle.service.add_dislike_to_post(post.content_id, service_bundle.stranger.user_id)

    rating = await service_bundle.service.add_dislike_to_post(post.content_id, service_bundle.stranger.user_id)

    assert rating.likes_count == 0
    assert rating.dislikes_count == 1


@pytest.mark.anyio
async def test_cannot_react_to_draft_post(service_bundle: ServiceBundle) -> None:
    post = service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="draft",
        status=ContentStatusEnum.DRAFT,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(19),
    )

    with pytest.raises(PostNotFound):
        await service_bundle.service.add_like_to_post(post.content_id, service_bundle.author.user_id)


@pytest.mark.anyio
async def test_cannot_react_to_deleted_post(service_bundle: ServiceBundle) -> None:
    post = service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="deleted",
        status=ContentStatusEnum.DELETED,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(20),
        deleted_at=dt(21),
    )

    with pytest.raises(PostNotFound):
        await service_bundle.service.add_like_to_post(post.content_id, service_bundle.author.user_id)


@pytest.mark.anyio
async def test_private_published_post_accepts_reaction_only_from_visible_user(service_bundle: ServiceBundle) -> None:
    post = service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="private",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PRIVATE,
        created_at=dt(22),
        published_at=dt(22),
    )

    owner_rating = await service_bundle.service.add_like_to_post(post.content_id, service_bundle.author.user_id)

    assert owner_rating.my_reaction == ReactionTypeEnum.LIKE

    with pytest.raises(PostNotFound):
        await service_bundle.service.add_like_to_post(post.content_id, service_bundle.stranger.user_id)


@pytest.mark.anyio
async def test_post_list_returns_my_reaction_correctly(service_bundle: ServiceBundle) -> None:
    first = service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="first",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(23),
        published_at=dt(23),
    )
    second = service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="second",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(24),
        published_at=dt(24),
    )
    service_bundle.repository.reactions[(first.content_id, service_bundle.stranger.user_id)] = ReactionTypeEnum.LIKE
    first.likes_count = 1

    posts = await service_bundle.service.get_posts(
        order=PostOrder.CREATED_AT,
        desc=True,
        offset=0,
        limit=10,
        user=service_bundle.stranger,
    )

    by_id = {post.post_id: post for post in posts}
    assert by_id[first.content_id].my_reaction == ReactionTypeEnum.LIKE
    assert by_id[second.content_id].my_reaction is None


@pytest.mark.anyio
async def test_subscriptions_list_returns_my_reaction_correctly(service_bundle: ServiceBundle) -> None:
    post = service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="subscription",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(25),
        published_at=dt(25),
    )
    service_bundle.repository.reactions[(post.content_id, service_bundle.follower.user_id)] = ReactionTypeEnum.DISLIKE
    post.dislikes_count = 1

    posts = await service_bundle.service.get_user_subscriptions_posts(
        user_id=service_bundle.follower.user_id,
        order=PostOrder.CREATED_AT,
        desc=True,
        offset=0,
        limit=10,
    )

    assert len(posts) == 1
    assert posts[0].my_reaction == ReactionTypeEnum.DISLIKE


@pytest.mark.anyio
async def test_feed_does_not_include_private_posts(service_bundle: ServiceBundle) -> None:
    service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="public",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(26),
        published_at=dt(26),
    )
    service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="private",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PRIVATE,
        created_at=dt(27),
        published_at=dt(27),
    )

    posts = await service_bundle.service.get_posts(
        order=PostOrder.CREATED_AT,
        desc=True,
        offset=0,
        limit=10,
        user=service_bundle.stranger,
    )

    assert [post.content for post in posts] == ["public"]


@pytest.mark.anyio
async def test_feed_does_not_include_drafts(service_bundle: ServiceBundle) -> None:
    service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="public",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(28),
        published_at=dt(28),
    )
    service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="draft",
        status=ContentStatusEnum.DRAFT,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(29),
    )

    posts = await service_bundle.service.get_posts(
        order=PostOrder.CREATED_AT,
        desc=True,
        offset=0,
        limit=10,
        user=service_bundle.stranger,
    )

    assert [post.content for post in posts] == ["public"]


@pytest.mark.anyio
async def test_author_profile_public_filter_returns_only_public_published(service_bundle: ServiceBundle) -> None:
    service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="public",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(30),
        published_at=dt(30),
    )
    service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="private",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PRIVATE,
        created_at=dt(31),
        published_at=dt(31),
    )
    service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="draft",
        status=ContentStatusEnum.DRAFT,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(32),
    )

    posts = await service_bundle.service.get_posts(
        order=PostOrder.CREATED_AT,
        desc=True,
        offset=0,
        limit=10,
        user_id=service_bundle.author.user_id,
        user=service_bundle.author,
        profile_filter=PostProfileFilter.PUBLIC,
    )

    assert [post.content for post in posts] == ["public"]


@pytest.mark.anyio
async def test_author_profile_all_filter_returns_all_non_deleted_posts(service_bundle: ServiceBundle) -> None:
    service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="public",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(32),
        published_at=dt(32),
    )
    service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="private",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PRIVATE,
        created_at=dt(33),
        published_at=dt(33),
    )
    service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="draft",
        status=ContentStatusEnum.DRAFT,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(34),
    )
    service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="deleted",
        status=ContentStatusEnum.DELETED,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(35),
        deleted_at=dt(36),
    )

    posts = await service_bundle.service.get_posts(
        order=PostOrder.CREATED_AT,
        desc=True,
        offset=0,
        limit=10,
        user_id=service_bundle.author.user_id,
        user=service_bundle.author,
        profile_filter=PostProfileFilter.ALL,
    )

    assert [post.content for post in posts] == ["draft", "private", "public"]


@pytest.mark.anyio
async def test_author_profile_private_filter_returns_only_private_published(service_bundle: ServiceBundle) -> None:
    service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="public",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(33),
        published_at=dt(33),
    )
    service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="private",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PRIVATE,
        created_at=dt(34),
        published_at=dt(34),
    )

    posts = await service_bundle.service.get_posts(
        order=PostOrder.CREATED_AT,
        desc=True,
        offset=0,
        limit=10,
        user_id=service_bundle.author.user_id,
        user=service_bundle.author,
        profile_filter=PostProfileFilter.PRIVATE,
    )

    assert [post.content for post in posts] == ["private"]


@pytest.mark.anyio
async def test_author_profile_drafts_filter_returns_only_drafts(service_bundle: ServiceBundle) -> None:
    service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="draft",
        status=ContentStatusEnum.DRAFT,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(35),
    )
    service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="public",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(36),
        published_at=dt(36),
    )

    posts = await service_bundle.service.get_posts(
        order=PostOrder.CREATED_AT,
        desc=True,
        offset=0,
        limit=10,
        user_id=service_bundle.author.user_id,
        user=service_bundle.author,
        profile_filter=PostProfileFilter.DRAFTS,
    )

    assert [post.content for post in posts] == ["draft"]


@pytest.mark.anyio
async def test_other_profile_does_not_show_private_or_drafts(service_bundle: ServiceBundle) -> None:
    service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="public",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(37),
        published_at=dt(37),
    )
    service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="private",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PRIVATE,
        created_at=dt(38),
        published_at=dt(38),
    )
    service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="draft",
        status=ContentStatusEnum.DRAFT,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(39),
    )

    posts = await service_bundle.service.get_posts(
        order=PostOrder.CREATED_AT,
        desc=True,
        offset=0,
        limit=10,
        user_id=service_bundle.author.user_id,
        user=service_bundle.stranger,
        profile_filter=PostProfileFilter.DRAFTS,
    )

    assert [post.content for post in posts] == ["public"]


@pytest.mark.anyio
async def test_deleted_posts_do_not_appear_in_regular_lists(service_bundle: ServiceBundle) -> None:
    service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="visible",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(40),
        published_at=dt(40),
    )
    service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="deleted",
        status=ContentStatusEnum.DELETED,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(41),
        deleted_at=dt(42),
    )

    feed = await service_bundle.service.get_posts(
        order=PostOrder.CREATED_AT,
        desc=True,
        offset=0,
        limit=10,
        user=service_bundle.stranger,
    )
    profile = await service_bundle.service.get_posts(
        order=PostOrder.CREATED_AT,
        desc=True,
        offset=0,
        limit=10,
        user_id=service_bundle.author.user_id,
        user=service_bundle.author,
        profile_filter=PostProfileFilter.PUBLIC,
    )

    assert [post.content for post in feed] == ["visible"]
    assert [post.content for post in profile] == ["visible"]
