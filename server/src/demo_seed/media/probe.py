from __future__ import annotations

import json
import subprocess
from pathlib import Path


def probe_video(path: Path) -> dict:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration,size:stream=width,height,bit_rate",
        "-of",
        "json",
        str(path),
    ]
    process = subprocess.run(command, capture_output=True, text=True, check=False)
    if process.returncode != 0:
        return {}
    try:
        return json.loads(process.stdout)
    except json.JSONDecodeError:
        return {}
