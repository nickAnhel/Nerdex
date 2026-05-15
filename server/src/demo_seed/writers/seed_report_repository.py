from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_json_report(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2, default=str)
    return path
