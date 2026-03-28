---
name: add-fastapi-feature
description: Implement or substantially change a FastAPI backend feature in Nerdex `server/src/`. Use when adding endpoints, services, repositories, DTOs, permissions, migrations, or async backend flows, especially if the change can affect content rules, visibility, ownership, counters, or S3 and media behavior.
---

# Add a FastAPI Feature in Nerdex Backend

Используй этот skill, когда задача добавляет или существенно меняет backend feature в `server/src/`.

## Goal
Реализовать backend functionality так, чтобы она уважала module boundaries, async patterns, unified content direction и migration discipline проекта Nerdex.

## Before writing code
Сначала проверь:
- target module structure,
- nearby routers / schemas / services / repositories,
- existing exceptions и handlers,
- относится ли change к `content`, `posts` или другому module owner,
- затрагивает ли change DB schema или S3/media behavior.

## Required implementation order
1. Define the use case.
2. Decide module ownership.
3. Define or update DTOs.
4. Update service methods.
5. Update repository methods.
6. Update router wiring.
7. Add migration, если меняется schema.
8. Update tests.

## Design rules
- Router остается thin.
- Service владеет business rules, permissions, orchestration, status transitions и cross-module coordination.
- Repository владеет SQLAlchemy query details.
- Naming должен быть explicit.
- Async flow должен сохраняться end-to-end.

## Mandatory checks
Перед завершением проверь, влияет ли feature на:
- authentication / authorization,
- visibility,
- publication status,
- ownership,
- counters,
- feed/profile projections,
- comments / reactions / tags,
- file/media lifecycle.

## Output expectations
Полная реализация обычно включает:
- code в correct module layer,
- migration при необходимости,
- DTO updates,
- error handling,
- tests или минимум test updates.

## Anti-patterns
Не делай:
- business logic inside router functions,
- прямой DB access из несвязанных модулей,
- copy-paste больших кусков соседнего модуля без улучшения abstraction,
- случайное добавление sync I/O в request flow.
