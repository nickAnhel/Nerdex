# Skill: Design PostgreSQL entity for Nerdex

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
Если entity связана с posts / articles / videos / courses / comments / reactions / tags / feed behavior, сначала реши, находится ли concern в shared `content` или в type-specific detail table.

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
