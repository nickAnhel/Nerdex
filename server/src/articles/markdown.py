from __future__ import annotations

import math
import re
import uuid
from dataclasses import dataclass

from src.articles.exceptions import InvalidArticle


DIRECTIVE_LINE_RE = re.compile(r"^::(?P<name>[a-z_]+)\{(?P<attrs>.*)\}\s*$")
SPOILER_OPEN_RE = re.compile(r"^:::spoiler(?:\[(?P<title>[^\]]{0,120})\])?\s*$")
ATTRIBUTE_RE = re.compile(r'(?P<key>[a-z][a-z0-9_-]*)="(?P<value>[^"]*)"')
RAW_HTML_RE = re.compile(r"<[A-Za-z!/][^>]*>")
YOUTUBE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
HEADING_RE = re.compile(r"^(#{2,3})\s+(.+?)\s*$")
BODY_H1_RE = re.compile(r"^#\s+")
SIZE_CHOICES = {"narrow", "wide", "full"}
WORD_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9_]+")
UUID_ATTR_KEYS = {
    "image": ("asset-id", "inline"),
    "video": ("asset-id", "video_source"),
}
LEADING_MARKDOWN_RE = re.compile(r"^(?:>\s*|[-*+]\s+|\d+\.\s+|\[[ xX]\]\s+)+")
IMAGE_LINK_RE = re.compile(r"!\[(?P<alt>[^\]]*)\]\([^)]+\)")
MARKDOWN_LINK_RE = re.compile(r"\[(?P<label>[^\]]+)\]\([^)]+\)")
INLINE_FORMATTING_RE = re.compile(r"(`+|[*_~]+)")


@dataclass(slots=True)
class ArticleAssetReference:
    asset_id: uuid.UUID
    attachment_type: str


@dataclass(slots=True)
class ArticleMarkdownAnalysis:
    excerpt: str
    word_count: int
    reading_time_minutes: int
    toc: list[dict[str, str | int]]
    asset_references: list[ArticleAssetReference]


def slugify_title(value: str) -> str:
    normalized = value.strip().lower()
    normalized = re.sub(r"[^a-zа-яё0-9]+", "-", normalized)
    normalized = normalized.strip("-")
    return normalized[:180] or "article"


def normalize_slug(value: str) -> str:
    normalized = slugify_title(value)
    if not normalized:
        raise InvalidArticle("Article slug cannot be empty")
    return normalized


def analyze_article_markdown(body_markdown: str) -> ArticleMarkdownAnalysis:
    lines = body_markdown.splitlines()
    plain_segments: list[str] = []
    toc: list[dict[str, str | int]] = []
    asset_references: list[ArticleAssetReference] = []

    in_code_block = False
    inside_spoiler = False

    for raw_line in lines:
        line = raw_line.rstrip()
        stripped = line.strip()

        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue

        if in_code_block:
            continue

        if RAW_HTML_RE.search(line):
            raise InvalidArticle("Raw HTML is not allowed in article markdown")

        if BODY_H1_RE.match(stripped):
            raise InvalidArticle("Article body must not contain an H1 heading")

        if stripped == ":::":
            if not inside_spoiler:
                raise InvalidArticle("Unexpected spoiler closing marker")
            inside_spoiler = False
            continue

        spoiler_match = SPOILER_OPEN_RE.match(stripped)
        if spoiler_match:
            inside_spoiler = True
            spoiler_title = (spoiler_match.group("title") or "").strip()
            if spoiler_title:
                plain_segments.append(spoiler_title)
            continue

        directive_match = DIRECTIVE_LINE_RE.match(stripped)
        if directive_match:
            directive_name = directive_match.group("name")
            attrs = _parse_attributes(directive_match.group("attrs"))
            if directive_name in UUID_ATTR_KEYS:
                asset_key, attachment_type = UUID_ATTR_KEYS[directive_name]
                asset_value = attrs.get(asset_key)
                if not asset_value:
                    raise InvalidArticle(f"Directive {directive_name} requires {asset_key}")
                try:
                    asset_id = uuid.UUID(asset_value)
                except ValueError as exc:
                    raise InvalidArticle(f"Directive {directive_name} has an invalid asset-id") from exc
                size = attrs.get("size", "wide")
                if size not in SIZE_CHOICES:
                    raise InvalidArticle(f"Directive {directive_name} has unsupported size {size}")
                asset_references.append(
                    ArticleAssetReference(
                        asset_id=asset_id,
                        attachment_type=attachment_type,
                    )
                )
                if attrs.get("caption"):
                    plain_segments.append(attrs["caption"])
                continue
            if directive_name == "youtube":
                youtube_id = attrs.get("id")
                if not youtube_id or not YOUTUBE_ID_RE.fullmatch(youtube_id):
                    raise InvalidArticle("Directive youtube requires a valid YouTube video id")
                if attrs.get("title"):
                    plain_segments.append(attrs["title"])
                continue
            raise InvalidArticle(f"Unsupported markdown directive {directive_name}")

        if stripped.startswith("::") or stripped.startswith(":::"):
            raise InvalidArticle("Unknown markdown directive syntax")

        heading_match = HEADING_RE.match(stripped)
        if heading_match:
            level = len(heading_match.group(1))
            text = heading_match.group(2).strip()
            if not text:
                continue
            anchor = slugify_title(text)
            toc.append(
                {
                    "level": level,
                    "text": text,
                    "anchor": anchor,
                }
            )
            plain_segments.append(_normalize_plain_text_fragment(text))
            continue

        if stripped:
            plain_segments.append(_normalize_plain_text_fragment(stripped))

    if in_code_block:
        raise InvalidArticle("Unclosed fenced code block in article markdown")
    if inside_spoiler:
        raise InvalidArticle("Unclosed spoiler block in article markdown")

    plain_text = "\n".join(plain_segments).strip()
    word_count = len(WORD_RE.findall(plain_text))
    reading_time_minutes = max(1, math.ceil(word_count / 200)) if plain_text else 1
    excerpt = _build_excerpt(plain_text)

    return ArticleMarkdownAnalysis(
        excerpt=excerpt,
        word_count=word_count,
        reading_time_minutes=reading_time_minutes,
        toc=toc,
        asset_references=asset_references,
    )


def _parse_attributes(raw_attrs: str) -> dict[str, str]:
    attrs = {match.group("key"): match.group("value") for match in ATTRIBUTE_RE.finditer(raw_attrs)}
    remaining = ATTRIBUTE_RE.sub(" ", raw_attrs).strip()
    if remaining:
        raise InvalidArticle("Directive attributes must use key=\"value\" format")
    return attrs


def _build_excerpt(plain_text: str) -> str:
    if not plain_text:
        return ""

    normalized = re.sub(r"\s+", " ", plain_text).strip()
    if len(normalized) <= 280:
        return normalized
    return normalized[:277].rstrip() + "..."


def _normalize_plain_text_fragment(value: str) -> str:
    normalized = LEADING_MARKDOWN_RE.sub("", value.strip())
    normalized = IMAGE_LINK_RE.sub(lambda match: match.group("alt").strip(), normalized)
    normalized = MARKDOWN_LINK_RE.sub(lambda match: match.group("label").strip(), normalized)
    normalized = INLINE_FORMATTING_RE.sub("", normalized)
    normalized = normalized.replace("\\", "")
    return normalized.strip()
