from __future__ import annotations

from pathlib import Path

from src.demo_seed.loaders._yaml import load_yaml


def load_templates(path: Path) -> dict:
    return load_yaml(path)
