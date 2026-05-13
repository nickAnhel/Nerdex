---
name: add-content-type
description: Extend the Nerdex unified content model with a new publishable content type such as posts, articles, or videos. Use when designing or implementing a new content type, or when refactoring an existing type to fit shared content semantics for feed, profile, search, permissions, reactions, comments, tags, and media lifecycle.
---

# Add a New Content Type to the Unified Content System

Используй этот skill, когда вводится или развивается новый publishable content type: posts, articles, videos и т.д.

## Goal
Расширить unified content architecture Nerdex без клонирования целых подсистем под каждый новый тип.

## Working model
Shared concerns должны жить в base content layer:
- author,
- type,
- status,
- visibility,
- timestamps,
- tags,
- comments,
- reactions,
- shared feed/profile semantics.

Type-specific concerns должны жить в detail tables/models.

## Design sequence
1. Define what is shared vs type-specific.
2. Extend enums и base content only if concern truly shared.
3. Add or update detail model/table.
4. Decide how type appears in feed / profile / search.
5. Decide media/storage needs.
6. Decide moderation / analytics implications, если релевантно.
7. Update DTO and serialization shape.
8. Update tests.

## Required questions
До реализации ответь:
- Какие поля живут в `content`?
- Какие поля живут в detail table?
- Какие queries должны оставаться shared across content types?
- Какие permissions и visibility rules shared?
- Какие type-specific read models нужны?
- Влияет ли change на comments / reactions / tags / feed cards / profile tabs?

## Anti-patterns
Не делай:
- дублирование всей логики из `posts` в новый module без выделения shared concerns,
- перенос type-specific fields в base table без сильной причины,
- разрушение feed/profile consistency между content types,
- игнорирование migration и backfill strategy.
