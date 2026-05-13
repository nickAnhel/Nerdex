---
name: design-postgres-entity
description: Design or change PostgreSQL-backed entities, relations, constraints, indexes, and migrations for Nerdex. Use when introducing schema for content, comments, reactions, tags, chats, media metadata, or any query-sensitive data model that must be driven by write and read paths, ownership, visibility, and future extensibility.
---

# Design a PostgreSQL Entity for Nerdex

Используй этот skill, когда задача вводит или меняет PostgreSQL-backed entity, relation или query-sensitive schema.

## Goal
Спроектировать schema, которая корректна для реального product behavior, а не просто syntactically complete.

## Process
1. Identify the domain object and its lifecycle.
2. Identify write paths.
3. Identify read paths.
4. Determine ownership and visibility rules.
5. Choose table boundaries.
6. Add constraints and indexes based on actual queries.
7. Plan migration and backfill impact.

## Required thinking
Всегда рассуждай про:
- primary key strategy,
- foreign keys и delete behavior,
- uniqueness constraints,
- enum usage,
- timestamp semantics,
- pagination / sorting / filtering queries,
- counters и denormalized fields,
- moderation / deletion / archive states, если релевантно.

## Content-specific rule
Если entity связана с posts / articles / videos / comments / reactions / tags / feed behavior, сначала реши, находится ли concern в shared `content` или в type-specific detail table.

## Deliverable format
При предложении schema changes включай:
- table purpose,
- key columns,
- constraints,
- indexes,
- expected query patterns,
- migration notes,
- trade-offs.

## Anti-patterns
Не делай:
- design только от UI labels,
- отсутствие indexes для очевидных list/feed/profile access paths,
- попытку держать core integrity только в Python, если SQL может enforce это лучше,
- premature denormalization без реального read bottleneck.
