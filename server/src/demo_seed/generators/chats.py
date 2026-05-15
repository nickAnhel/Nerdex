from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass

from src.chats.enums import ChatMemberRole, ChatType
from src.events.enums import EventType
from src.demo_seed.planning.plans import PlannedChat, PlannedEvent, PlannedMembership, PlannedTimelineItem, PlannedUser
from src.demo_seed.planning.random_state import SeedRandom
from src.demo_seed.planning.time_distribution import TimeDistributor

CHAT_TITLE_MAX_LENGTH = 64


@dataclass(slots=True)
class ChatsPlan:
    chats: list[PlannedChat]
    memberships: list[PlannedMembership]
    events: list[PlannedEvent]
    timeline_items: list[PlannedTimelineItem]


def _direct_key(left: uuid.UUID, right: uuid.UUID) -> str:
    a, b = sorted([str(left), str(right)])
    return f"{a}:{b}"


def _format_demo_chat_title(seed_run_id: str, suffix: str) -> str:
    prefix = f"[DEMO:{seed_run_id}] "
    max_suffix_length = CHAT_TITLE_MAX_LENGTH - len(prefix)
    if max_suffix_length <= 0:
        return prefix[:CHAT_TITLE_MAX_LENGTH]
    if len(suffix) <= max_suffix_length:
        return prefix + suffix
    if max_suffix_length <= 3:
        return (prefix + suffix)[:CHAT_TITLE_MAX_LENGTH]
    return prefix + suffix[:max_suffix_length - 3].rstrip() + "..."


def build_chats(
    *,
    random: SeedRandom,
    distributor: TimeDistributor,
    users: list[PlannedUser],
    seed_run_id: str,
    min_count: int,
    max_count: int,
) -> ChatsPlan:
    target = random.randint(min_count, max_count)
    chats: list[PlannedChat] = []
    memberships: list[PlannedMembership] = []
    events: list[PlannedEvent] = []
    timeline: list[PlannedTimelineItem] = []

    direct_count = int(target * 0.45)
    group_count = target - direct_count

    used_direct: set[str] = set()

    # Direct chats.
    while len([chat for chat in chats if chat.chat_type == ChatType.DIRECT.value]) < direct_count:
        left = random.choice(users)
        right = random.choice(users)
        if left.user_id == right.user_id:
            continue
        d_key = _direct_key(left.user_id, right.user_id)
        if d_key in used_direct:
            continue
        used_direct.add(d_key)
        chat_id = uuid.uuid4()
        title = _format_demo_chat_title(
            seed_run_id,
            f"Direct {left.display_name} / {right.display_name}",
        )
        chat = PlannedChat(
            chat_id=chat_id,
            owner_id=left.user_id,
            title=title,
            chat_type=ChatType.DIRECT.value,
            is_private=True,
            direct_key=d_key,
        )
        chats.append(chat)
        memberships.append(PlannedMembership(chat_id=chat_id, user_id=left.user_id, role=ChatMemberRole.OWNER.value))
        memberships.append(PlannedMembership(chat_id=chat_id, user_id=right.user_id, role=ChatMemberRole.MEMBER.value))

        event_id = uuid.uuid4()
        event_created = distributor.random_content_created_at()
        events.append(
            PlannedEvent(
                event_id=event_id,
                event_type=EventType.CREATE.value,
                created_at=event_created,
                user_id=left.user_id,
                altered_user_id=right.user_id,
                chat_id=chat_id,
            )
        )
        timeline.append(
            PlannedTimelineItem(
                chat_id=chat_id,
                chat_seq=1,
                item_type="event",
                message_id=None,
                event_id=event_id,
            )
        )

    # Group chats.
    while len([chat for chat in chats if chat.chat_type == ChatType.GROUP.value]) < group_count:
        owner = random.choice(users)
        members_count = random.randint(3, min(12, len(users)))
        members = {owner.user_id}
        for user in random.sample(users, members_count):
            members.add(user.user_id)
        chat_id = uuid.uuid4()
        topic_slug = max(owner.interests, key=owner.interests.get)
        title = _format_demo_chat_title(
            seed_run_id,
            f"{topic_slug.replace('_', ' ').title()} Group {len(chats)+1}",
        )
        chat = PlannedChat(
            chat_id=chat_id,
            owner_id=owner.user_id,
            title=title,
            chat_type=ChatType.GROUP.value,
            is_private=False,
            direct_key=None,
        )
        chats.append(chat)
        for member_id in members:
            role = ChatMemberRole.OWNER.value if member_id == owner.user_id else ChatMemberRole.MEMBER.value
            memberships.append(PlannedMembership(chat_id=chat_id, user_id=member_id, role=role))

        created = distributor.random_content_created_at()
        create_event_id = uuid.uuid4()
        events.append(
            PlannedEvent(
                event_id=create_event_id,
                event_type=EventType.CREATE.value,
                created_at=created,
                user_id=owner.user_id,
                altered_user_id=None,
                chat_id=chat_id,
            )
        )
        timeline.append(
            PlannedTimelineItem(chat_id=chat_id, chat_seq=1, item_type="event", message_id=None, event_id=create_event_id)
        )

        seq = 1
        for member_id in sorted(members):
            if member_id == owner.user_id:
                continue
            seq += 1
            event_id = uuid.uuid4()
            events.append(
                PlannedEvent(
                    event_id=event_id,
                    event_type=EventType.JOIN.value,
                    created_at=distributor.random_after(created, min_minutes=1, max_days=2),
                    user_id=owner.user_id,
                    altered_user_id=member_id,
                    chat_id=chat_id,
                )
            )
            timeline.append(
                PlannedTimelineItem(chat_id=chat_id, chat_seq=seq, item_type="event", message_id=None, event_id=event_id)
            )

    return ChatsPlan(chats=chats, memberships=memberships, events=events, timeline_items=timeline)
