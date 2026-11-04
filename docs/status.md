# Implementation status

Updated: 5 November 2026 (Asia/Karachi).

## Delivered in this slice

- Project structure, local configuration example, locked Python/npm dependencies, Alembic initial migration, startup launcher, and proposed CI/Compose recipes.
- PostgreSQL-backed collections, originals, immutable text passages, ingestion jobs, job events, and fixture investigations.
- Exact citation validation and navigation data; analyst review decisions/notes and revision conflict handling.
- Persisted state, cancellation, ingestion retry, lease recovery/fencing, stale-result invalidation, source/collection deletion, and derived-text cleanup.
- Next.js editorial library, claim desk, evidence board, source reader, history, review controls, and Markdown downloads.
- Explicit fixture labeling; custom source/claim analysis fails honestly instead of simulating a general live model.

## Milestone interpretation

M0–M2 functionality has been implemented, with specific acceptance gaps: browser acceptance/real screenshots are blocked in this environment, the clean Docker/CI path has not been executed, and the full release/security/evaluation documentation remains future work. Do not mark these milestones fully accepted solely from code presence. This is not a completed EvidenceLens v1.

Next work is M3: restricted PDF ingestion and source-version/recovery behavior. M4 introduces real embeddings/retrieval and live provider adapters. M5–M6 add measured AI gates, product/security verification, and a reproducible portfolio release. No other portfolio application has been started.

## Repository and publishing

The application lives in its own project directory. No GitHub remote, public repository, license grant, or hosting has been created. Source-control initialization and verification are recorded in the final work report, not inferred from this document.

## Known deviations from the proposed plan

- This slice supports `.txt` only, with a 2 MiB cap. Planned PDF support and the larger binary-file cap are not shipped.
- Uploads are raw streamed bodies rather than multipart, so receive-time limits apply without a pre-spooled parser.
- Documents are immutable single-source records; full replacement versions and embedding generations are not implemented yet.
- Fixture analysis uses known passages and claims, not real embeddings or a live model. No AI quality baseline or numeric model thresholds have been established.
- Reviewed Markdown is generated from a locked current snapshot in one bounded request, rather than persisted export jobs/artifacts.
- Worker tasks are deliberately short. Long tasks need heartbeats/checkpoints and expanded failure policy before PDF/model execution.

These are declared milestone boundaries, not substitutions for final v1 acceptance.
