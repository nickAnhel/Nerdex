# Skill: Add React feature in Nerdex frontend

Используй этот skill, когда задача добавляет или заметно меняет UI flow в `client/src/`.

## Goal
Сделать frontend feature, которая вписывается в текущий React + Router + MobX style и при этом движет проект к более clean и reusable product surfaces.

## Before writing code
Сначала изучи:
- related pages / components / stores / http modules,
- route structure,
- current DTO/API usage,
- existing loading/error/empty-state patterns,
- относится ли surface к одному конкретному content type или должна проектироваться как shared content UI.

## Implementation order
1. Clarify user flow.
2. Identify route/page/component entry points.
3. Identify API/store changes.
4. Implement UI state handling.
5. Wire optimistic updates только если rollback/refetch behavior ясен.
6. Remove dead code, вызванный изменением.

## UI rules
- Backend is the source of truth.
- Request logic должен быть centralized.
- Предпочитай reusable primitives для content/media actions.
- Всегда обрабатывай loading, empty, error и permission-sensitive states.
- Будь аккуратен с route nesting и state reset при navigation.

## Unified content guidance
Когда затрагиваются feed, profile, cards, reactions, comments или content lists:
- не overfit implementation под один конкретный content type,
- предпочитай shared fields + type-specific rendering extensions,
- не хардкодь assumptions, блокирующие articles/videos/courses later.

## Anti-patterns
Не делай:
- duplicated API logic во множестве components,
- hidden business rules в presentation components,
- brittle effects, вызывающие repeated requests,
- optimistic updates там, где consistency важнее perceived speed.
