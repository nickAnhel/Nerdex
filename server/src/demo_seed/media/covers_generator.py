from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw


@dataclass(slots=True)
class GeneratedCover:
    filename: str
    mime_type: str
    payload: bytes
    width: int
    height: int


TOPIC_COLORS: dict[str, tuple[int, int, int]] = {
    "frontend": (0, 102, 204),
    "backend": (16, 132, 80),
    "databases": (165, 102, 28),
    "devops": (110, 88, 176),
    "ai_ml": (7, 120, 126),
    "security": (170, 45, 45),
    "product_ux": (200, 83, 53),
    "education_career": (90, 106, 41),
}


def generate_technical_cover(*, topic: str, title: str, keywords: list[str], width: int = 1280, height: int = 720) -> GeneratedCover:
    base_color = TOPIC_COLORS.get(topic, (80, 100, 120))
    image = Image.new("RGB", (width, height), base_color)
    draw = ImageDraw.Draw(image)

    draw.rectangle((40, 40, width - 40, height - 40), outline=(255, 255, 255), width=3)
    draw.text((70, 80), topic.replace("_", " ").upper(), fill=(255, 255, 255))
    draw.text((70, 140), title[:90], fill=(255, 255, 255))
    draw.text((70, 220), ", ".join(keywords[:5]), fill=(230, 230, 230))

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=85)
    payload = buffer.getvalue()
    filename = f"{topic}_cover.jpg"
    return GeneratedCover(
        filename=filename,
        mime_type="image/jpeg",
        payload=payload,
        width=width,
        height=height,
    )


def generate_initials_avatar(*, initials: str, width: int = 512, height: int = 512) -> GeneratedCover:
    image = Image.new("RGB", (width, height), (30, 30, 30))
    draw = ImageDraw.Draw(image)
    draw.ellipse((28, 28, width - 28, height - 28), fill=(70, 130, 200))
    draw.text((width // 2 - 24, height // 2 - 18), initials[:2].upper(), fill=(255, 255, 255))

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    payload = buffer.getvalue()
    return GeneratedCover(
        filename="avatar.png",
        mime_type="image/png",
        payload=payload,
        width=width,
        height=height,
    )
