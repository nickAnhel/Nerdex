from __future__ import annotations

import re

from src.demo_seed.loaders.models import TopicDefinition
from src.demo_seed.planning.random_state import SeedRandom


def _slugify(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9\s-]", "", value.lower())
    text = re.sub(r"\s+", "-", text).strip("-")
    return text[:160] or "article"


def build_post_text(random: SeedRandom, topic: TopicDefinition, angle: str, tags: list[str]) -> tuple[str, str, str]:
    title = f"{topic.title}: Practical Notes on {angle.title()}"
    excerpt = f"A concise breakdown of {angle} for {topic.title.lower()} workflows."
    body = (
        f"I tested a workflow around {angle} in a production-like setup. "
        f"The strongest results came from keeping the contract explicit, documenting edge cases, "
        f"and validating behavior with small repeatable checks. Tags: {', '.join(tags)}."
    )
    return title, excerpt, body


def build_article_text(random: SeedRandom, topic: TopicDefinition, angle: str, tags: list[str]) -> tuple[str, str, str, int, int, list[dict], str]:
    title = f"{topic.title} Deep Dive: {angle.title()}"
    intro = f"This article explains a practical approach to {angle} in {topic.title.lower()}."
    sections = [
        "Problem framing",
        "Implementation details",
        "Failure modes",
        "Operational checklist",
        "Summary",
    ]
    markdown = [f"# {title}", "", intro, ""]
    for index, section in enumerate(sections, start=1):
        markdown.append(f"## {index}. {section}")
        markdown.append(
            f"Use explicit contracts and measurable outcomes for {angle}. "
            f"Focus on constraints, migration safety, and predictable developer workflows."
        )
        markdown.append("")
    markdown.append(f"Related tags: {', '.join(tags)}")
    body_markdown = "\n".join(markdown)
    words = len(body_markdown.split())
    reading_minutes = max(1, round(words / 220))
    toc = [{"text": section, "level": 2, "anchor": _slugify(section)} for section in sections]
    slug = _slugify(title)
    return title, intro, body_markdown, words, reading_minutes, toc, slug


def build_video_text(random: SeedRandom, topic: TopicDefinition, angle: str, tags: list[str]) -> tuple[str, str, str, list[dict]]:
    title = f"{topic.title} Walkthrough: {angle.title()}"
    excerpt = f"A technical walkthrough with practical implementation details for {angle}."
    description = (
        f"This video covers design decisions, trade-offs, and implementation checks for {angle}. "
        f"It includes an applied example and quality checklist. Tags: {', '.join(tags)}."
    )
    chapters = [
        {"title": "Context", "startsAtSeconds": 0},
        {"title": "Implementation", "startsAtSeconds": 20},
        {"title": "Validation", "startsAtSeconds": 45},
    ]
    return title, excerpt, description, chapters


def build_moment_text(random: SeedRandom, topic: TopicDefinition, angle: str, tags: list[str]) -> tuple[str, str, str]:
    title = f"{topic.title} Moment: {angle.title()}"
    excerpt = f"Short technical moment about {angle}."
    caption = f"Quick update on {angle}. Main tags: {', '.join(tags)}."
    return title, excerpt, caption


def build_comment_text(random: SeedRandom, topic: str, content_title: str) -> str:
    templates = [
        "Useful breakdown of {title}. I would also benchmark the edge case path.",
        "This is clear and practical. The permission checks around {topic} are especially important.",
        "Good explanation. I tested a similar approach and transaction ordering mattered a lot.",
        "Strong point on maintainability. Adding small invariants first usually saves time later.",
    ]
    template = random.choice(templates)
    return template.format(title=content_title[:80], topic=topic)


def build_chat_message_text(random: SeedRandom, topic: str) -> str:
    templates = [
        "Can you share your checklist for {topic} rollout?",
        "I reviewed the latest {topic} update and it looks ready for validation.",
        "Let us compare implementation notes for {topic} after the next deploy.",
        "I attached a draft file with tasks for the {topic} milestone.",
    ]
    return random.choice(templates).format(topic=topic.replace("_", " "))
