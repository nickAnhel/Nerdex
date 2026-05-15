from __future__ import annotations

from collections import defaultdict
import uuid

from src.demo_seed.planning.plans import PlannedContent, PlannedUser


def build_expected_interests_report(*, users: list[PlannedUser], contents: list[PlannedContent]) -> list[dict]:
    content_by_author: dict[uuid.UUID, list[PlannedContent]] = defaultdict(list)
    for content in contents:
        content_by_author[content.author_id].append(content)

    report: list[dict] = []
    for user in users:
        authored = content_by_author.get(user.user_id, [])
        topic_counts: dict[str, int] = defaultdict(int)
        type_counts: dict[str, int] = defaultdict(int)
        for content in authored:
            topic_counts[content.topic] += 1
            type_counts[content.content_type.value] += 1

        report.append(
            {
                "user_id": str(user.user_id),
                "username": user.username,
                "topic_interests": user.interests,
                "expected_tags": user.expected_tags,
                "expected_author_topics": [
                    topic for topic, _count in sorted(topic_counts.items(), key=lambda item: item[1], reverse=True)[:5]
                ],
                "expected_content_types": type_counts,
            }
        )

    return report
