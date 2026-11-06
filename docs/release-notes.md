# Local v1 candidate release notes

5 November2026.

This update completes the remaining local implementation after the initial text/fixture slice: PDF parsing/rendering, versioned sources, pgvector hybrid retrieval, live adapter contracts, confirmed claims/revisions, stored exports/provenance, stronger jobs/limits/cleanup, browser checks, Docker setup, and measured fixture evaluation.

The source and all project development now live directly at /Users/apple/Desktop/evidencelens. Existing original PostgreSQL data was copied into a separate pgvector development database before migration; the older PostgreSQL installation was preserved. The source-build output uses .next-v1 so an older running frontend's .next is preserved.

## Upgrade

Back up the database and matching artifact directory together. Install the pinned runtime/development requirements and frontend lockfile. PostgreSQL17 with vector is the supported reproducible runtime. An administrator must install the vector extension before Alembic upgrade; migrations backfill existing documents into version1 families. Existing originals are not rewritten. Rebuild the selected embedding profile before investigating migrated sources.

The default fresh local database uses port55432 and the artifact directory .local/v1-artifacts. Do not point an upgraded process at an older database schema, or start old/new workers against the same migrated database.

## Acceptance boundary

Fixture acceptance is reproducible. A later [bounded Gemini text development run](live-validation.md) provides partial live-generation compatibility evidence; PDF generation, semantic embedding quality and broader model acceptance remain incomplete. No v2 work, GitHub publication, public hosting, or open-source license grant is included.
