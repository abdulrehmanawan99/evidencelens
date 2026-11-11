# Local v1 candidate release notes

## 11 November 2026: documentation

- Architecture now has a public component diagram, a job-state diagram and an
  architecture decisions table. It also states which provider was exercised live.

5 November2026.

This update completes the remaining local implementation after the initial text/fixture slice: PDF parsing/rendering, versioned sources, pgvector hybrid retrieval, live adapter contracts, confirmed claims/revisions, stored exports/provenance, stronger jobs/limits/cleanup, browser checks, Docker setup, and measured fixture evaluation.

The source build writes to `.next-v1`, so an older frontend build in `.next` is left alone.

## Upgrade

Back up the database and matching artifact directory together. Install the pinned runtime/development requirements and frontend lockfile. PostgreSQL17 with vector is the supported reproducible runtime. An administrator must install the vector extension before Alembic upgrade; migrations backfill existing documents into version1 families. Existing originals are not rewritten. Rebuild the selected embedding profile before investigating migrated sources.

The default fresh local database uses port55432 and the artifact directory .local/v1-artifacts. Do not point an upgraded process at an older database schema, or start old/new workers against the same migrated database.

## Acceptance boundary

Fixture acceptance is reproducible. [Bounded Gemini development runs](live-validation.md) provide partial live-generation compatibility evidence; the current v5 analysis was rejected by Gemini (HTTP 400), and PDF generation, semantic embedding quality and broader model acceptance remain incomplete. No v2 work or public hosting is included.
