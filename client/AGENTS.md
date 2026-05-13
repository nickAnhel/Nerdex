# Client AGENTS.md

## Scope
Этот файл применяется ко всему `client/`.

## Current repo facts
Frontend использует React, React Router, MobX, Axios, Socket.IO и page/component/store/http style structure.

## Роль frontend в этом проекте
Frontend — это product client, а не primary home для domain truth.
Backend владеет business rules, permissions, visibility, publication state и file access rules.
Frontend владеет presentation, interaction flow, local UI state, request lifecycle и optimistic UX только там, где это безопасно.

## Rules
- Держи API interaction centralized.
- Не дублируй request logic по компонентам без сильной причины.
- Не зашивай domain invariants в local component state.
- MobX stores и UI state должны отражать backend contracts, а не подменять их.
- Всегда проектируй loading, empty, error и permission-sensitive states.
- Не делай optimistic update, если не продуман rollback/refetch behavior.
- Убирай dead UI paths и obsolete props/store branches после refactor.

## API and data flow
- Используй stable API clients / http-layer abstraction.
- DTO shape должна приходить с backend; frontend может делать только presentation-oriented adaptation.
- Не размазывай serialization/deserialization details по разным components.
- Если API contract слабый, сначала предложи улучшение контракта, а не компенсируй проблему fragile UI-логикой.

## Component and page design
- Думай через page flow, feature boundaries и reusable primitives.
- Для крупных surfaces предпочитай clear separation: page / feature block / reusable UI.
- Не перенасыщай page-level components сетевыми побочными эффектами и сложной orchestration logic.
- Route transitions, modal states, drawer states и form states должны быть предсказуемыми.

## Unified content guidance
Когда меняешь feed, profile, cards, reactions, comments или content lists:
- не overfit implementation под один конкретный content type,
- выделяй shared fields и shared interaction patterns,
- добавляй type-specific rendering extension points,
- не хардкодь assumptions, которые заблокируют articles/videos позже.

## Media/UI guidance
- Media rendering должно исходить из coherent backend media model.
- Не считай raw URL единственной истиной, если backend отдает richer file DTO.
- Для avatar / attachment / preview surfaces всегда продумывай loading, fallback, broken-file и permission cases.

## Strong preferences
Предпочитай:
- clear user flow,
- explicit component responsibilities,
- centralized request handling,
- predictable state transitions,
- scalable UI patterns.

Избегай:
- hidden business logic inside components,
- duplicated request code,
- effect-driven refetch storms,
- ad-hoc state duplication по дереву компонентов.

## Done criteria
Frontend change не считается complete, если:
- не обработаны UI states,
- API integration остается incoherent,
- не покрыты очевидные edge cases,
- не убран dead code, появившийся после change.
