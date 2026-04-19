import uuid

import pytest

from src.articles.exceptions import InvalidArticle
from src.articles.markdown import analyze_article_markdown, slugify_title


def test_analyze_article_markdown_builds_toc_excerpt_and_asset_references() -> None:
    image_id = uuid.uuid4()
    video_id = uuid.uuid4()

    analysis = analyze_article_markdown(
        "\n".join(
            [
                "## Intro",
                "First paragraph for excerpt.",
                f'::image{{asset-id="{image_id}" size="wide" caption="Architecture"}}',
                "### Details",
                f'::video{{asset-id="{video_id}" size="full" caption="Demo"}}',
                '::youtube{id="dQw4w9WgXcQ" title="Video"}',
                "```mermaid",
                "flowchart TD",
                "A-->B",
                "```",
            ]
        )
    )

    assert analysis.word_count > 0
    assert analysis.reading_time_minutes >= 1
    assert analysis.excerpt.startswith("Intro First paragraph")
    assert [item["text"] for item in analysis.toc] == ["Intro", "Details"]
    assert [item.asset_id for item in analysis.asset_references] == [image_id, video_id]


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("<div>bad</div>", "Raw HTML"),
        ("# Heading\ntext", "H1"),
        ("::youtube{id=\"bad\"}", "YouTube"),
    ],
)
def test_analyze_article_markdown_rejects_invalid_input(body: str, message: str) -> None:
    with pytest.raises(InvalidArticle, match=message):
        analyze_article_markdown(body)


def test_slugify_title_normalizes_to_stable_path_segment() -> None:
    assert slugify_title("  Hello, Nerdex Articles!  ") == "hello-nerdex-articles"


def test_analyze_article_markdown_strips_markdown_formatting_from_excerpt() -> None:
    analysis = analyze_article_markdown(
        "\n".join(
            [
                "## Intro",
                "> **Quoted** line",
                "- [Linked value](https://example.com)",
                "1. `Code` item",
            ]
        )
    )

    assert analysis.excerpt == "Intro Quoted line Linked value Code item"
