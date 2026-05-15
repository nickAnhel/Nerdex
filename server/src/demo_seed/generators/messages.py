from __future__ import annotations

import uuid
from dataclasses import dataclass

from src.content.enums import ContentStatusEnum, ContentTypeEnum, ContentVisibilityEnum
from src.content.enums import ReactionTypeEnum
from src.demo_seed.planning.plans import (
    PlannedChat,
    PlannedContent,
    PlannedMembership,
    PlannedMessage,
    PlannedMessageAsset,
    PlannedMessageReaction,
    PlannedMessageSharedContent,
    PlannedTimelineItem,
)
from src.demo_seed.planning.random_state import SeedRandom
from src.demo_seed.planning.text_plans import build_chat_message_text
from src.demo_seed.planning.time_distribution import TimeDistributor
from src.videos.enums import VideoProcessingStatusEnum


@dataclass(slots=True)
class MessagesPlan:
    messages: list[PlannedMessage]
    reactions: list[PlannedMessageReaction]
    shared_content: list[PlannedMessageSharedContent]
    message_assets: list[PlannedMessageAsset]
    timeline_items: list[PlannedTimelineItem]


def _is_shareable_content_for_chat(content: PlannedContent) -> bool:
    if content.status != ContentStatusEnum.PUBLISHED:
        return False
    if content.visibility != ContentVisibilityEnum.PUBLIC:
        return False
    if content.content_type in {ContentTypeEnum.VIDEO, ContentTypeEnum.MOMENT}:
        if content.playback_status != VideoProcessingStatusEnum.READY:
            return False
    return True


def build_messages(
    *,
    random: SeedRandom,
    distributor: TimeDistributor,
    chats: list[PlannedChat],
    memberships: list[PlannedMembership],
    contents: list[PlannedContent],
    file_asset_ids: list[uuid.UUID],
    min_count: int,
    max_count: int,
    reactions_min: int,
    reactions_max: int,
    initial_seq_by_chat: dict[uuid.UUID, int] | None = None,
) -> MessagesPlan:
    target = random.randint(min_count, max_count)
    messages: list[PlannedMessage] = []
    timeline: list[PlannedTimelineItem] = []
    reactions: list[PlannedMessageReaction] = []
    shared: list[PlannedMessageSharedContent] = []
    message_assets: list[PlannedMessageAsset] = []

    members_by_chat: dict[uuid.UUID, list[uuid.UUID]] = {}
    seq_by_chat: dict[uuid.UUID, int] = dict(initial_seq_by_chat or {})
    for membership in memberships:
        members_by_chat.setdefault(membership.chat_id, []).append(membership.user_id)

    shareable_contents = [item for item in contents if _is_shareable_content_for_chat(item)]

    while len(messages) < target and chats:
        chat = random.choice(chats)
        members = members_by_chat.get(chat.chat_id) or []
        if not members:
            continue
        sender = random.choice(members)
        topic = chat.title.split(" ")[1] if " " in chat.title else "backend"
        created_at = distributor.random_content_created_at()
        message_id = uuid.uuid4()
        message = PlannedMessage(
            message_id=message_id,
            client_message_id=uuid.uuid4(),
            chat_id=chat.chat_id,
            user_id=sender,
            content=build_chat_message_text(random, topic),
            created_at=created_at,
            reply_to_message_id=None,
        )
        if messages and random.random() <= 0.22:
            target_message = random.choice([item for item in messages if item.chat_id == chat.chat_id] or messages)
            message.reply_to_message_id = target_message.message_id
            if message.created_at < target_message.created_at:
                message.created_at = distributor.random_after(target_message.created_at, min_minutes=1, max_days=2)

        messages.append(message)
        seq = seq_by_chat.get(chat.chat_id, 0) + 1
        seq_by_chat[chat.chat_id] = seq
        timeline.append(
            PlannedTimelineItem(
                chat_id=chat.chat_id,
                chat_seq=seq,
                item_type="message",
                message_id=message.message_id,
                event_id=None,
            )
        )

        if random.random() <= 0.18 and shareable_contents:
            content = random.choice(shareable_contents)
            shared.append(PlannedMessageSharedContent(message_id=message.message_id, content_id=content.content_id))
        if random.random() <= 0.15 and file_asset_ids:
            message_assets.append(
                PlannedMessageAsset(
                    message_id=message.message_id,
                    asset_id=random.choice(file_asset_ids),
                    sort_order=0,
                )
            )

    reaction_target = random.randint(reactions_min, reactions_max)
    used: set[tuple[str, str]] = set()
    while len(reactions) < reaction_target and messages:
        message = random.choice(messages)
        members = members_by_chat.get(message.chat_id) or []
        if not members:
            continue
        user_id = random.choice(members)
        if user_id == message.user_id:
            continue
        key = (str(message.message_id), str(user_id))
        if key in used:
            continue
        used.add(key)
        reactions.append(
            PlannedMessageReaction(
                message_id=message.message_id,
                user_id=user_id,
                reaction_type=random.choice([
                    ReactionTypeEnum.LIKE,
                    ReactionTypeEnum.HEART,
                    ReactionTypeEnum.FIRE,
                    ReactionTypeEnum.JOY,
                    ReactionTypeEnum.CLAP,
                ]),
                created_at=distributor.random_after(message.created_at, min_minutes=1, max_days=30),
            )
        )

    messages.sort(key=lambda item: item.created_at)
    return MessagesPlan(
        messages=messages,
        reactions=reactions,
        shared_content=shared,
        message_assets=message_assets,
        timeline_items=timeline,
    )
