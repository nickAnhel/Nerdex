from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class TopicTag:
    slug: str
    title: str
    weight: float


@dataclass(slots=True)
class TopicDefinition:
    slug: str
    title: str
    description: str
    weight: float
    tags: list[TopicTag]
    adjacent_topics: dict[str, float]
    content_angles: list[str]


@dataclass(slots=True)
class TopicsConfig:
    version: int
    topics: dict[str, TopicDefinition]


@dataclass(slots=True)
class FeaturedUserConfig:
    username: str
    display_name: str
    role: str
    bio: str
    links: list[dict[str, str]]
    interests: dict[str, float]
    preferred_content_types: dict[str, float]
    expected_tags: list[str]
    author_profile: dict[str, Any]
    presentation_note: str


@dataclass(slots=True)
class FeaturedUsersEnvelope:
    version: int
    defaults: dict[str, Any]
    featured_users: list[FeaturedUserConfig]


@dataclass(slots=True)
class MediaTopicQueries:
    categories: list[str] = field(default_factory=list)
    image_queries: list[str] = field(default_factory=list)
    video_queries: list[str] = field(default_factory=list)
    moment_queries: list[str] = field(default_factory=list)
    generated_cover_keywords: list[str] = field(default_factory=list)
    negative_keywords: list[str] = field(default_factory=list)


@dataclass(slots=True)
class MediaQueriesEnvelope:
    version: int
    provider: str
    defaults: dict[str, Any]
    topics: dict[str, MediaTopicQueries]
