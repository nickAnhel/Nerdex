# AGENTS.md

## Что это за проект
Nerdex — это social network / knowledge-sharing platform с упором на unified content architecture.
Product direction опирается на unified content model и допускает развитие в сторону нескольких publishable content types, а также profiles, comments, reactions, subscriptions, chats, messages, events и media в S3-compatible storage.

Repository layout:
- `client/` — React frontend
- `server/` — FastAPI backend
- `docker-compose.yaml` — локальная dev entrypoint

Всегда считай backend source of truth для:
- domain rules,
- permissions,
- visibility,
- publication state,
- counters,
- file/media access.

## Текущий технологический контекст
- Frontend: React, React Router, MobX, Axios, Socket.IO.
- Backend: FastAPI, SQLAlchemy 2.x, Alembic, asyncpg, aiobotocore, SQLAdmin, uvicorn.
- Main DB: PostgreSQL.
- File storage: S3-compatible object storage.
- Unified `content` model является базовым слоем publishable content. Любой type-specific behavior должен наследоваться от этой модели через detail tables, projections и application logic.

## Архитектурный вектор
Предпочитай решения, которые усиливают следующие направления:
1. Unified content core со shared semantics для feed / search / reactions / comments.
2. Thin routers, явный service layer, явный repository/data-access layer.
3. Async backend code.
4. Private-object storage model с backend-controlled access.
5. DB constraints и migrations вместо неявных допущений в коде.
6. Frontend как consumer стабильных backend contracts, а не как место, где живет domain truth.

## Non-negotiable rules
- Не вводи architectural shortcuts, которые противоречат unified content direction.
- Не клади business logic в FastAPI routers.
- Не ходи в DB напрямую из несвязанных модулей, если уже есть service/repository boundary.
- Не меняй schema без Alembic migration.
- Не делай permanent public URL основой доступа к файлу, если достаточно stable object key + backend-controlled access.
- Не выноси domain invariants в React-only state.
- Не добавляй Neo4j, если задача не выигрывает от graph traversal/querying заметно сильнее, чем от PostgreSQL.
- Не сохраняй слабые legacy patterns только потому, что они уже есть; если migration cost разумный, предпочитай cleaner target design.

## Backend expectations
- Весь новый backend flow должен быть async-first.
- Организуй изменения по module boundaries: `users`, `posts`, `content`, `comments`, `tags`, `s3`, `chats`, `messages`, `events` и т.д.
- Внутри модуля предпочитай такую форму, когда она уместна:
  - `router.py` — HTTP/transport layer only
  - `schemas.py` — request/response DTOs
  - `service.py` — use cases, permissions, orchestration, transaction thinking
  - `repository.py` — SQLAlchemy queries и persistence details
  - `models.py` — ORM mapping
  - `exceptions.py` / `exc_handlers.py` — domain exceptions и HTTP mapping
- Permission checks должны быть явными.
- Всегда продумывай ownership, visibility, publication state, counters и idempotency.

## Database expectations
- Предпочитай UUID primary keys.
- Добавляй explicit indexes под реальные query paths.
- Кодируй invariants через constraints там, где это возможно.
- Проектируй schema от read/write paths, а не только от списка сущностей.
- Для content-related schema всегда думай о feed queries, author profile queries, moderation и будущем появлении новых content types.
- Не вводи denormalization без конкретного read bottleneck.

## S3 / file storage expectations
- По умолчанию исходи из one private bucket model, если задача явно не требует иного.
- Если файл значим для domain, metadata должна жить в DB.
- Считай `object_key`, `owner_id`, `mime_type`, `size`, `checksum`, `purpose`, `lifecycle_state` first-class concerns.
- Upload/download access обычно должен идти через backend-issued URLs или backend-mediated authorization.
- Derived assets (`thumbnail`, `preview`, etc.) должны иметь deterministic lifecycle rules.

## Frontend expectations
- Frontend должен потреблять backend DTOs / APIs, а не реконструировать domain truth на своей стороне.
- API access должен быть centralized.
- Всегда обрабатывай loading / empty / error / partial states.
- Не дублируй request logic по дереву компонентов.
- Для новой feature думай о page flow, permissions, optimistic updates, rollback и edge cases.

## Protocol работы над задачей
Если реализуется feature или refactor:
1. Сначала прочитай ближайшие `AGENTS.md`, которые относятся к зоне изменений.
2. Изучи affected module structure до начала правок.
3. Если change non-trivial — сначала сформулируй target design.
4. Делай smallest coherent change set, который двигает дизайн вперед.
5. Держи naming в рамках существующего domain language, если нет сильной причины улучшить его.
6. Если текущая реализация слабая — улучшай ее осознанно, а не копируй слабость дальше.

## Definition of done
Изменение не считается complete, если при необходимости не выполнены:
- code changes в correct layer,
- schema migration для DB changes,
- обновление DTOs/contracts,
- permission handling,
- error handling,
- tests или минимум test updates для измененного поведения,
- удаление dead paths, которые change сделал obsolete.

## Что оптимизировать
Оптимизируй решения под:
- reliability,
- maintainability,
- clean boundaries,
- scalability of the content system,
- practical extension to articles/videos,
- predictable developer workflow.

