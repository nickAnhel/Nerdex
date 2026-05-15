from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class PersonaTemplate:
    role: str
    display_prefix: str
    bio_template: str
    publication_rate: str
    engagement_level: str


DEFAULT_PERSONAS = [
    PersonaTemplate(
        role="active_author",
        display_prefix="Author",
        bio_template="Engineering author focused on {topic_title}.",
        publication_rate="high",
        engagement_level="high",
    ),
    PersonaTemplate(
        role="popular_author",
        display_prefix="Popular",
        bio_template="Popular contributor writing practical notes about {topic_title}.",
        publication_rate="medium",
        engagement_level="very_high",
    ),
    PersonaTemplate(
        role="active_commenter",
        display_prefix="Commenter",
        bio_template="Community member discussing {topic_title} with detailed comments.",
        publication_rate="low",
        engagement_level="high",
    ),
    PersonaTemplate(
        role="regular_user",
        display_prefix="User",
        bio_template="Learner exploring {topic_title} and related engineering practices.",
        publication_rate="low",
        engagement_level="medium",
    ),
    PersonaTemplate(
        role="cold_start_user",
        display_prefix="Starter",
        bio_template="New member interested in {topic_title} and curated technical materials.",
        publication_rate="low",
        engagement_level="low",
    ),
]
