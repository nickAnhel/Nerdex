---
name: review-architecture-change
description: Review a non-trivial refactor, subsystem, or cross-cutting architecture change in Nerdex. Use when evaluating proposals that affect unified content design, service and repository boundaries, API contracts, PostgreSQL schema, S3 and media storage, frontend and backend responsibilities, migration cost, extensibility, or operational risk.
---

# Review an Architecture Change for Nerdex

Используй этот skill, когда задача предлагает non-trivial refactor, новый subsystem или cross-cutting design change.

## Goal
Оценить, делает ли proposed change Nerdex более reliable, scalable и maintainable.

## Review frame
Оцени proposal по следующим осям:
- domain boundaries,
- API design,
- database impact,
- storage/media impact,
- frontend impact,
- migration cost,
- backward compatibility,
- operational risk,
- future extensibility.

## Project-specific focus points
Особенно внимательно смотри на:
- unified content consistency,
- S3/media consistency,
- backend service/repository layering,
- feed/profile/reactions/comments coupling,
- действительно ли Neo4j justified,
- не заставляют ли frontend хранить backend truth.

## Output format
Верни:
1. verdict,
2. strongest benefits,
3. main risks,
4. better alternative, если текущая идея слабая,
5. recommended implementation path.

## Anti-patterns
Флагай особенно сильно, если proposal:
- размазывает domain rules по многим слоям,
- добавляет schema без query justification,
- вводит second competing content model,
- создает one-off media flow, несовместимый с target storage architecture.
