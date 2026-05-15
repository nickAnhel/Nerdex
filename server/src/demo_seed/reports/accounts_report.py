from __future__ import annotations

from src.demo_seed.planning.plans import PlannedUser


def build_accounts_report(*, users: list[PlannedUser], password_source: str) -> dict:
    featured = []
    generated = []
    for user in users:
        item = {
            "username": user.username,
            "password_source": password_source,
            "display_name": user.display_name,
            "interests": user.interests,
            "expected_tags": user.expected_tags,
            "presentation_note": user.presentation_note_en,
        }
        if user.is_featured:
            featured.append(item)
        else:
            generated.append(item)

    return {
        "featured_users": featured,
        "generated_users": generated,
    }
