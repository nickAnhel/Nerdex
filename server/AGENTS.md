# Server AGENTS.md

## Scope
Этот файл применяется ко всему `server/`.

## Stack и текущая форма backend
Backend в этом репозитории использует FastAPI, SQLAlchemy 2.x, Alembic, asyncpg, aiobotocore, SQLAdmin и uvicorn.
Код организован по domain modules внутри `server/src/`, включая `users`, `posts`, `content`, `comments`, `tags`, `chats`, `messages`, `events`, `s3`.

## Required architectural style
Используй module-oriented layered backend design:
- router = transport layer
- service = use cases + orchestration + permissions + transaction boundaries
- repository = persistence/query details
- models = ORM mapping
- schemas = DTOs

## Rules for routers
- Routers должны оставаться thin.
- Router может парсить input, собирать dependencies и возвращать DTO.
- Router не должен содержать business rules, SQLAlchemy queries или object storage logic.
- Router не должен silently swallow domain exceptions.

## Rules for services
- Service владеет use-case logic.
- Service проверяет ownership, visibility, status transitions и cross-module orchestration.
- Service — это место, где осознанно проектируются transaction boundaries.
- Если use case затрагивает и DB, и S3, явно продумывай operation ordering, failure modes и compensating actions.
- Предпочитай one public service method per clear use case.

## Rules for repositories
- Repository владеет SQLAlchemy query composition.
- Repository отвечает за filtering, eager loading strategy, pagination, locking needs.
- Не протаскивай ORM details в routers.
- Query shape должна соответствовать реальным read paths.
- Всегда проверяй N+1 risks.

## Schema and model rules
- Любое schema change требует Alembic migration.
- Используй explicit names для tables, indexes, constraints и enums.
- Server defaults добавляй только если они реально согласованы с application logic.
- Используй timezone-aware timestamps.
- Всегда продумывай delete behavior и `ondelete` semantics.
- Для content-related tables сохраняй совместимость с unified content direction.

## Async rules
- Весь новый backend code должен быть async-first.
- Не вводи blocking I/O в request path.
- Если third-party library blocking, изолируй это явно и вызывай осознанно.

## API contract rules
- DTOs должны быть explicit и stable.
- Разделяй request schemas и response schemas, когда это упрощает контракт.
- Не светить внутренние ORM details в API payloads.
- Предпочитай backward-compatible API changes, если задача явно не допускает breakage.

## Permissions and visibility
Всегда рассуждай про:
- owner access,
- public/private/link-only visibility,
- draft/published/archived/deleted states,
- subscriber-only или user-context-sensitive behavior,
- moderation impact, если это релевантно.

Никогда не предполагай, что “authenticated” означает “allowed”.

## Media and S3
- Object storage access должен быть за service/adapter boundary.
- Не разбрасывай raw S3 logic по модулям.
- Для domain-significant files предпочитай DB-backed file metadata.
- Avatars, post media, article attachments, video assets, thumbnails и previews должны укладываться в coherent storage model.

## Unified content guidance
В проекте `content` — это unified base model для publishable content. Type-specific modules должны расширять ее через detail tables, service logic и serialization rules.
При развитии content features:
- shared concerns держи в `content`,
- type-specific fields — в detail tables/models,
- не клонируй одну и ту же логику в каждый новый content type,
- сначала думай о shared base для feed/profile/reactions/comments, а потом о type-specific details.

## Testing expectations
Для meaningful backend changes добавляй или обновляй tests на:
- service behavior,
- repository query behavior, если query non-trivial,
- API behavior для critical paths,
- permission/visibility edge cases.

## Strong preferences
Предпочитай:
- explicit method names,
- explicit types,
- explicit failure handling,
- explicit transaction thinking,
- coherent refactors вместо patchy local hacks.

Избегай:
- magic helpers, скрывающих domain behavior,
- подхода “просто скопируй один из существующих type-specific modules и слегка поправь” при проектировании нового content type,
- неаккуратного хранения derived counters,
- смешения responsibilities между content base и content details.
