from __future__ import annotations

from dataclasses import dataclass

from src.demo_seed.planning.random_state import SeedRandom


@dataclass(slots=True)
class GeneratedFile:
    filename: str
    mime_type: str
    payload: bytes


DEFAULT_FILES: list[tuple[str, str, str]] = [
    ("react-component-checklist.pdf", "application/pdf", "React component checklist\n- props contract\n- loading state\n- error state\n"),
    ("fastapi-service-layer-notes.pdf", "application/pdf", "FastAPI service layer notes\n- permission checks\n- repository boundaries\n"),
    ("postgresql-indexes-cheatsheet.pdf", "application/pdf", "PostgreSQL indexes cheatsheet\n- btree\n- gin\n- partial indexes\n"),
    ("docker-compose-template.yml", "text/yaml", "services:\n  api:\n    image: nerdex-api\n"),
    ("neo4j-recommendations-draft.md", "text/markdown", "# Neo4j recommendations draft\n\nGraph schema notes.\n"),
    ("jwt-auth-flow.json", "application/json", '{"flow": ["login", "issue_token", "refresh"]}\n'),
    ("deployment-commands.txt", "text/plain", "docker compose pull\ndocker compose up -d\n"),
]


def generate_files(random: SeedRandom, count: int) -> list[GeneratedFile]:
    files: list[GeneratedFile] = []
    for i in range(count):
        filename, mime_type, content = DEFAULT_FILES[i % len(DEFAULT_FILES)]
        content_with_suffix = content + f"\n# generated_variant={i}\n"
        files.append(GeneratedFile(filename=filename, mime_type=mime_type, payload=content_with_suffix.encode("utf-8")))
    return files
