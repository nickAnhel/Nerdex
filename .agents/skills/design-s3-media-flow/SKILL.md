---
name: design-s3-media-flow
description: Design or refactor S3-compatible media flows in Nerdex. Use when working on uploads, downloads, avatars, post media, article attachments, video files, thumbnails, previews, object keys, file metadata, backend-issued access, lifecycle states, or orphan cleanup in the project's private-bucket storage model.
---

# Design an S3 and Media Flow for Nerdex

Используй этот skill, когда работа идет над avatars, post media, article attachments, video files, thumbnails, previews или любым object-storage-backed file flow.

## Goal
Построить storage flow, который secure, maintainable и совместим с private-bucket, backend-controlled access model.

## Required model
Думай в двух слоях:
1. Object storage layer — actual binary object в S3-compatible storage.
2. Domain metadata layer — DB record, описывающий ownership, purpose, type, state и lifecycle.

## Minimum metadata to reason about
Для domain-significant files продумывай минимум:
- file_id,
- owner_id,
- object_key,
- bucket,
- mime_type,
- size,
- checksum/etag, если полезно,
- purpose/category,
- visibility/access policy,
- processing state,
- created_at/deleted_at.

## Flow design checklist
Определи:
- upload initiation,
- validation,
- object key strategy,
- timing создания DB record,
- post-upload confirmation, если требуется,
- generation of derivative assets,
- access/download strategy,
- delete/archive behavior,
- orphan cleanup behavior,
- error recovery.

## Project-specific guidance
- По умолчанию предпочитай one private bucket model, если task requirements явно не требуют иного.
- Не делай raw public URLs source of truth.
- Avatar/media logic должна двигаться к single coherent storage model, а не к набору one-off file paths.
- Если текущая реализация fragmented, сначала спроектируй target model, потом адаптируй ее поэтапно.

## Anti-patterns
Не делай:
- хранение только URL как будто design уже complete,
- смешивание authorization rules со случайным frontend code,
- ad-hoc S3 key naming между модулями,
- игнорирование lifecycle of derived files.
