# Codex CLI handoff — EvidenceLens and the ten-project portfolio

Prepared on 5 November 2026 for continuing this project from Codex CLI in Warp.

## Start here

Canonical repository: **`/Users/apple/Desktop/evidencelens`**.

Latest implementation commit: **`a248d8c` — Complete EvidenceLens local v1 candidate and verification**. Earlier commit: `699f54a`, the initial text/fixture workflow. The working tree was clean before this handoff was added. This handoff is a new documentation file; application code was not changed for the handoff.

**Current position: EvidenceLens local v1 is implemented as a release candidate. Actual model integration and quality acceptance remain outstanding.** Do not rebuild the app from scratch or describe it as fully AI-validated. Follow the updated three-project delivery policy below and in `AGENTS.md`.

Read this file, inspect the current checkout, then read these repository documents:

- `README.md`: installation, features, configuration, limits.
- `docs/status.md`: delivered scope and outstanding acceptance.
- `docs/architecture.md`: implementation architecture and data boundaries.
- `docs/verification.md`: checks actually executed and their limitations.
- `docs/providers.md`: provider contracts and evaluation procedure.
- `docs/threat-model.md`: local access, parsing, secrets, and deletion boundaries.
- `docs/release-notes.md`: upgrade and release notes.

These are historical project records. Recheck runtime/configuration before continuing, and follow the user's latest instructions if their priorities change.

### Continuation update

The user subsequently authorized three-project parallel development, private GitHub repositories and PRs under **`abdulrehmanawan99`**, and research/use of suitable free APIs. They dropped the requirement to see subagents inside Warp; built-in subagents are permitted. Local repositories for Webhook Clinic and CallMap now exist directly on the Desktop. Their first fixture milestones do not establish complete PRD or live-AI acceptance. The canonical scope remains `/Users/apple/Downloads/Ten_AI_Applications_PRD.md`, with newer user instructions taking precedence over its older delivery schedule. See `AGENTS.md` and `docs/free-providers.md`.

## User context and decisions

- Updated user instruction, 5 November 2026: these are **GitHub portfolio projects**, developed **three at a time**, with proportionate scope and no overengineering. This supersedes the earlier one-project-at-a-time instruction. The first batch is EvidenceLens, Webhook Clinic, and CallMap; a blocker in one must not prevent progress on the others. See `AGENTS.md` and `/Users/apple/Desktop/AGENTS.md`.
- Projects should live directly under the user's **Desktop**, with one repository per application. EvidenceLens is already in the correct location.
- EvidenceLens v1 is a **private local app first**. Hosted accounts and multitenancy have not been requested for this project.
- The user asked whether local apps can be pushed to GitHub. We explained that they can. No GitHub remote/publication, repository visibility, hosting, or project-wide license grant has been selected or created.
- The user is unfamiliar with AI terminology. Explain the product purpose and model choices in plain language before asking them to choose infrastructure or models.
- The user authorized remaining EvidenceLens v1 implementation; that work is committed. They have not selected a live provider or generation model.
- We suggested OpenAI as one possible convenient next step and explained how to add a key locally. **That suggestion is not a confirmed provider choice.** The user then asked for explanations of scope, architecture, and the full portfolio plan.
- Latest request: create this Markdown handoff so another Codex session can continue from the same context. Do not treat the handoff request itself as a new instruction to install models or call a paid API.

## What EvidenceLens actually does

EvidenceLens investigates **one selected claim against a collection of uploaded PDF/text documents**.

A claim is a statement such as: “Harbor Transit recorded 1.20 million journeys in Q2.” The user can type it or select a suggested claim from an extracted passage. Suggestions require confirmation before investigation.

The app retrieves relevant passages, proposes supporting/conflicting/contextual evidence, links findings to exact quotations and page/line references, lets the user review findings and add notes, and exports a cited Markdown brief.

The bundled synthetic reports deliberately contain:

- A final operations report stating 1.20 million journeys.
- A final board report stating 1.05 million for the same period/scope.
- An earlier provisional estimate of 1.10 million, which should be treated as context rather than another final measurement.
- A qualitative staff memo with no quantitative financial evidence.

This is claim-by-claim evidence review. It does not automatically compare every assertion in every document or establish objective truth beyond the supplied sources.

Current exclusions include unrestricted internet crawling, exhaustive fact checking, OCR for scanned/image-only PDFs, public hosting/accounts, and autonomous external actions. Human review remains part of the core workflow.

## AI concepts already explained to the user

- **Embedding model:** converts passages and a claim into numerical representations used for relevance search. The app combines vector search with keyword search.
- **Language/generation model:** interprets retrieved passages, proposes evidence relations, explains them, and can suggest claims.
- **Provider:** the service or local server running those models. Separate generation and embedding configurations are supported.
- We are using existing models, not training a new model.
- **Fixture mode:** predefined synthetic interpretations plus a hashed lexical demo index. It demonstrates the real application workflow but proves neither live model compatibility nor semantic quality.
- **Local application does not necessarily mean local inference.** Cloud embeddings send extracted text chunks to the configured service; cloud generation sends claims and selected passages. Local inference can instead run through an appropriate local server such as Ollama.

## Implemented architecture

```mermaid
flowchart TD
    Browser["Browser: React UI and PDF.js reader"] <--> Web["Next.js server and same-origin API proxy"]
    Web <--> API["FastAPI API"]
    API <--> DB[("PostgreSQL 17 + pgvector: records, passages, vectors, jobs")]
    API <--> Files[("Private originals and saved Markdown exports")]
    Worker["Python background worker"] <--> DB
    Worker <--> Files
    Worker <--> Parser["Isolated PDF parser"]
    Worker <--> Adapters["Generation and embedding adapters"]
    Adapters --> Fixture["Fixture mode: active at handoff"]
    Adapters -.-> Local["Optional local model server"]
    Adapters -.-> Cloud["Optional cloud provider"]
```

The durable queue is in PostgreSQL; EvidenceLens does not use Redis. Worker jobs include ingestion, investigation, reindexing, claim suggestions, provider checks, exports, and deletion. Jobs use renewed leases, fencing, bounded retries/deadlines/provider calls, cancellation, and guarded publication.

Document versions are immutable rows grouped into source families. Source changes invalidate previous analyses/exports. Embedding profiles fingerprint configuration and prevent incompatible vectors from mixing. Reindexing is explicit and publishes atomically.

The worker validates passage IDs, collection/source scope, context membership, and exact quotations before findings publish. Reviews use optimistic revision checks. Persisted exports freeze the reviewed snapshot and provenance; downloads check integrity and source validity.

PDF parsing is outside API/worker logic. Source-run macOS uses a dedicated Docker parser with no network and a read-only single-file mount. Linux uses a resource-limited subprocess; full Docker adds outer container restrictions. PDF.js displays the original page separately from exact extracted-text citations.

Deletion immediately revokes access, then background cleanup removes originals and derived data. Downloaded briefs and backups cannot be recalled. Manual claims remain after deleting only a source; collection deletion also clears claims/revisions. See the threat model for retained tombstone/operational metadata.

## Modules already delivered

Paths in this section are relative to the canonical repository.

- `backend/app/main.py`, `routes_v1.py`, `schemas.py`: core APIs, source/version/index/provider/claim/export routes, validation, and contracts.
- `backend/app/models.py`, `services.py`, `db.py`: persistence, local-owner access checks, quotas, source storage, revisions, and serialization.
- `backend/app/worker.py`: durable processing, leases, cancellation/recovery, publication, cleanup, and orphan sweeping.
- `backend/app/extraction.py`, `pdf_parser.py`: bounded extraction, page references, and parser isolation.
- `backend/app/providers.py`: fixture, OpenAI Responses, strict-schema compatible chat, Ollama, separate embeddings, response validation, and usage/error handling.
- `backend/app/retrieval.py`: scoped keyword/vector retrieval, fusion, context selection, profiles, and index status.
- `backend/app/exporting.py`: frozen review snapshots and cited Markdown rendering.
- `backend/migrations/versions/9a52d54b985e_pdf_versions_retrieval_provenance_and_.py`: current migration head; follows `4419783888ce`.
- `apps/web/app/page.tsx`, `components-v1.tsx`, `pdf-reader.tsx`, `globals.css`: editorial reading room, reviews, PDF/text sources, versions, suggestions, index/provider controls, provenance, and exports.
- `apps/web/lib/openapi.json`, `schema.d.ts`, `api.ts`: generated backend contracts and client helpers.
- `scripts/run-local.py`, `setup-local.py`, `compose.yaml`, Dockerfiles: local runtime and reproducible full Docker setup.
- `backend/tests/test_workflow.py`, `test_v1.py`: backend regression coverage.
- `apps/web/e2e.mjs`, `e2e-pdf.mjs`, `e2e-container.mjs`: text/PDF browser flows, accessibility, screenshots, Docker browser proxy.
- `fixtures/evaluation.json`, `scripts/evaluate.py`, `benchmark.py`: labeled evaluation cases and bounded fixture measurements.

Do not replace the existing editorial interface with a generic chatbot/dashboard. Its design uses cream backgrounds, ink typography, a source reader, and evidence comparison.

## Verification already performed

The following are **recorded results from 5 November 2026**, not new tests run merely by reading this handoff:

- 60 backend tests passed against actual PostgreSQL/pgvector.
- Alembic upgrades succeeded for an empty database and a copy of the old application database; schema check reported no new operations.
- OpenAPI generation/drift, TypeScript checks, and production builds passed.
- Text and PDF browser workflows passed on source-run services and the full Docker stack.
- Representative evidence/PDF reader accessibility scans reported zero violations. This is bounded automated coverage, not certification.
- A fresh Docker setup and claim/review/export persistence across container restart were verified.
- The fixture evaluation passed six scenarios: three known claims against both text and PDF samples, with six exact citations and full labeled passage/evidence recall. These are predefined regressions, not live quality scores.
- Python/npm dependency audits found no known advisories at the recorded time; Bandit reported no medium/high findings; a limited secret-pattern scan passed.
- Actual screenshots, example export, license inventory, workload measurements, and residual limits are in `docs/`.

One upstream Starlette warning about its httpx-based test client remains recorded. GitHub Actions is supplied but has not run remotely because there is no remote/push.

Important fixed regressions include keyword matching, contrast, context-group CSS, keyboard tabs, blank PDF pages, idle polling, retained-version recovery, and deletion of excluded-source names from old export snapshots. Keep those behaviors covered.

Rerun checks appropriate to actual changes; do not overwrite historical results with unexecuted claims or repeatedly rerun unchanged tests without a reason.

## Current machine/runtime snapshot

Checked while preparing this handoff on 5 November 2026 around 12:56 UTC:

- `.env` exists and `MODEL_MODE` is `fixture`.
- No nonempty `OPENAI_API_KEY`, `GENERATION_API_KEY`, or `EMBEDDING_API_KEY` was found in `.env`/the inspecting process environment. Only presence flags were inspected; no secrets are copied here.
- No Ollama executable was found in PATH.
- The existing `.env` Node override points to an available binary.
- No listener was observed on 3000, 3001, 8000, 8001, 55432, or 11434. A browser tab can still display an old localhost URL. Check Docker Desktop and current processes rather than assuming the app/database is running or missing.
- No Git remote was configured. Application working tree was clean before creating this file.

These facts can change immediately. Recheck them without dumping `.env` or credentials.

Previously verified host: macOS x86_64, 16 GiB RAM, Python 3.12.14, Node 24.19.0. The system Node 22.11 was too old for the current PDF.js build; use Node 22.13+ or preferably 24. The launcher honors `NODE_EXECUTABLE`; direct npm commands still need a supported Node in PATH.

Existing machine-specific Node path:

```text
/Users/apple/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node
```

The earlier desktop shell had restrictive permissions and required explicit access to the repo, network, and Docker socket. Warp/CLI may have different permissions. Diagnose current permissions rather than copying old sandbox workarounds blindly.

## Data and runtime preservation

- The app's pgvector database container is configured as `evidencelens-v1-db`, published on loopback port **55432**.
- Its persistent external volume is **`evidencelens_v1_pgdata`**. It was transitioned to Compose management with that same volume; do not replace/delete it casually.
- Databases created during development include `evidencelens`, `evidencelens_test_local`, and `evidencelens_browser`. Verify their existence before assuming they are available.
- Current development originals/exports use ignored **`.local/v1-artifacts`**. Preserve this directory together with the matching database.
- A private pre-upgrade SQL backup is in ignored **`.local/backups/pre-v1-backup.sql`**.
- The original native PostgreSQL 14 installation/database on port 5432 was preserved. Do not migrate or reset unrelated databases.
- Clean-install QA used a separate `evidencelens-v1-clean` Compose project, volume `evidencelens_v1_clean_pgdata`, ports 3100/8100/55433, and `.local/clean-artifacts`. Its containers were removed after checks; its external volume may remain.
- Source builds use **`.next-v1`**, preserving an older `.next` build. Do not rebuild into a directory used by another running Next instance with different API proxy settings. Prefer one launcher at a time or a genuinely isolated Docker/checkout setup.
- Never run backend tests against an application database. The test fixture deletes all application rows and requires a database name starting with **`evidencelens_test_`**.
- Do not overwrite existing `.env` with `.env.example`, remove persistent volumes, run global process-kill commands, or stop an unknown user-owned app to free ports.
- An older, stale copy may remain at `/Users/apple/Documents/Codex/2026-11-04/files-mentioned-by-the-user-ten/outputs/evidencelens`. Develop only in the Desktop repository. Do not delete the old copy as part of resuming.

## Starting the existing app

First inspect status, occupied ports, installed runtimes, Docker availability, and existing configuration. Current code is committed, so rebuilding/reinstalling everything is not automatically necessary.

### Source-run option

From the repository root, with Docker Desktop running and dependencies available:

```bash
cd /Users/apple/Desktop/evidencelens
python3 scripts/setup-local.py
docker compose up -d db
.venv/bin/python scripts/run-local.py --production
```

Default UI/API: `http://127.0.0.1:3000` and `http://127.0.0.1:8000`.

If another service occupies those ports, investigate before acting. The launcher supports `--port 3001 --api-port 8001`; avoid running simultaneous builds into the same web build directory.

The launcher reads `.env`, migrates, prepares PDF assets/parser, builds the UI, starts API/worker/UI, and waits for readiness. Ctrl+C stops that launcher's children, not the database. Production mode is the verified source-run path; the old sandbox had a development file-watcher issue.

### Full Docker option

Use this instead of, not concurrently with, a source-run stack on the same ports/database:

```bash
cd /Users/apple/Desktop/evidencelens
python3 scripts/setup-local.py
docker compose --profile app up --build -d
```

This provides db/API/worker/web. The external database volume and private artifact bind mount persist when containers stop. Preserve them.

If dependencies are actually missing, use Python 3.12 with `backend/requirements-dev.lock` for development and `npm ci --prefix apps/web` under a supported Node. Runtime images use `backend/requirements.lock`.

## The actual remaining v1 work

**Provider selection and real AI acceptance are the next milestone.** No provider/model has been confirmed by the user, and no live model call has been accepted so far.

1. Confirm the user's preferred setup after explaining cost/privacy/local hardware tradeoffs simply. If they already added configuration after this handoff, inspect it safely and use the new information rather than asking again.
2. Verify current official provider documentation, available model IDs, strict-schema support, embedding dimensions, limits, and terms. Do not copy old or deprecated model recommendations without checking.
3. Configure generation and embeddings separately in ignored server-side `.env`. No keys in chat, committed files, browser bundles, logs, screenshots, or parser environments. Avoid printing the complete configuration.
4. Restart the relevant API/worker safely and run the provider capability check.
5. Rebuild the collection index when the embedding profile changes. Do not mix vectors from different models/dimensions/configurations.
6. Run the development suite against synthetic data with a real provider. Inspect outcome correctness, citation validity, passage relevance, missing-evidence behavior, explanations, latency, and actual usage.
7. Establish and record numeric live quality gates from the measured development baseline, then freeze them before evaluating the held-out split. Never tune prompts/gates against held-out results and call the result untouched evaluation.
8. Run the five-case held-out split, including new entities, support/conflict, missing metrics, period mismatch, and document injection. Human review is needed in addition to automatic scoring.
9. Repeat the core workflow with a second real provider configuration when credentials/capabilities permit. Record any blocked configuration honestly.
10. Fix reproduced problems, run affected checks, and update provider/status/verification/release records. Only then assess complete v1 acceptance.

`docs/evaluation-live.json` currently records **blocked**. MockTransport tests only check adapter contracts. The fixture's successful scores and the small fixture performance workload cannot substitute for live model results or production capacity.

Do not start v2 features, hosted accounts, projects outside the active three-project batch, GitHub publication, or a cloud deployment merely because the fixture workflow works. The updated delivery policy permits parallel work on EvidenceLens, Webhook Clinic, and CallMap. There is no agreed v2 feature list yet.

## Relevant commands

Run from `/Users/apple/Desktop/evidencelens` unless a block changes directory. Check current mode before evaluations: live calls can incur provider usage and transmit text.

### Backend regression suite — disposable test database only

The DSN below uses the known development-only credentials from the repository's initializer/example, not a live provider secret.

```bash
export TEST_DATABASE_URL=postgresql+psycopg://evidencelens:evidencelens_local@127.0.0.1:55432/evidencelens_test_local
cd /Users/apple/Desktop/evidencelens/backend
DATABASE_URL="$TEST_DATABASE_URL" ../.venv/bin/python -m alembic upgrade head
../.venv/bin/python -m pytest -q --basetemp=../.local/cli-tests
DATABASE_URL="$TEST_DATABASE_URL" ../.venv/bin/python -m alembic check
```

On macOS keep parser-test files under the Desktop checkout so Docker can see the bind mounts. Previous Codex scratch locations were not visible to the Docker VM.

### Frontend and API contracts

Use a supported Node/npm pair:

```bash
cd /Users/apple/Desktop/evidencelens
.venv/bin/python scripts/export-openapi.py
npm run api:generate --prefix apps/web
npm run typecheck --prefix apps/web
npm run build --prefix apps/web
```

Do not rebuild a web directory in use by a different running instance. The generated contract files are tracked; inspect intentional drift.

### AI evaluation

Use the API port of the running validation instance:

```bash
.venv/bin/python scripts/evaluate.py --api http://127.0.0.1:8000 --suite fixture --output docs/evaluation-fixture.json
.venv/bin/python scripts/evaluate.py --api http://127.0.0.1:8000 --suite live --split development --output docs/evaluation-live.json
# Only after establishing and freezing the development gates:
.venv/bin/python scripts/evaluate.py --api http://127.0.0.1:8000 --suite live --split held_out --output docs/evaluation-live-held-out.json
```

The script creates/deletes its own synthetic collections. It exits with status 2 and records blocked coverage when the requested mode is unavailable. Keep distinct real configuration reports/provenance instead of overwriting them indiscriminately.

Browser commands, the Docker Playwright harness, audit commands/results, and screenshots are documented in `README.md` and `docs/verification.md`. Existing screenshots are genuine captures. Do not fabricate replacements or claim tests not executed.

## Portfolio plan — projects after EvidenceLens

Original PRD: `/Users/apple/Downloads/Ten_AI_Applications_PRD.md` (proposed portfolio scope, not proof of implementation). The delivery sequence below is different from the order of its application catalog.

Only EvidenceLens has been developed. Proposed build order:

1. **EvidenceLens** — claim evidence review across uploaded reports. Next.js/TypeScript, FastAPI API/worker, PostgreSQL/pgvector, private document storage.
2. **Webhook Clinic** — inspect failed deliveries, bounded diagnostics, reviewed replay to a controlled local receiver. React/Vite, Express/TypeScript, MongoDB, Redis. No arbitrary destinations or automatic production replay.
3. **CallMap** — audio transcription, timestamped commitments/owners/deadlines, corrections, export. React/Vite, FastAPI API/worker, PostgreSQL, Redis, audio storage. Synthetic/consented recordings; no live telephony or automatic contact.
4. **VisualInspect** — compare approved packaging artwork with a production image, review candidate discrepancies, export annotations. Vue/Vite, FastAPI image worker, PostgreSQL/image storage. Human review; no manufacturing certification.
5. **ClauseTrace** — compare two contract versions, align clauses, review changed obligations/deadlines, export a checklist. Next.js, FastAPI, PostgreSQL/document storage. No legal advice or automatic approval.
6. **ParcelProof** — organise order/delivery/message records, expose evidence gaps, review and export a dispute packet. React/Vite, NestJS, PostgreSQL, Redis/BullMQ. No live dispute submission in v1.
7. **Runbook Relay** — evidence-backed simulated incident investigation with bounded read-only tools, checkpoints, recovery, and review. React/Vite, FastAPI, PostgreSQL. No production remediation or arbitrary shell execution.
8. **Specimen** — controlled browser accessibility investigations with axe rules, screenshots, reproducible findings, and exports. Next.js, NestJS, isolated Playwright workers, PostgreSQL. No unrestricted third-party scanning or certification.
9. **SchemaGuard** — parse migration SQL, apply deterministic risk rules, explain findings, propose a reviewed rollout. Vue/Vite, Express/TypeScript, PostgreSQL. Submitted SQL is not executed in v1.
10. **Dependency Atlas** — inspect an allowed repository's manifests/dependency graph, investigate upgrade impact, and export source-linked plans. Next.js, NestJS, isolated Python worker, PostgreSQL/scoped graph adapter. No imported-code/install-script execution or automatic PR creation in v1. Graphify/“graphipy” meaning, suitability, license, and egress remain unresolved.

For each project: understand the user/problem → narrow one complete v1 workflow → design/interface/architecture/threat model → implement a working slice → persistence/provider integration → verification/security fixes → documentation/release.

Use distinct interfaces, real persistence, bounded jobs/tools, traceable sources, human review where required, synthetic/consented fixtures, and honest separation of fixture/live/unverified results. Local acceptance comes first; selected AWS/Terraform reference deployments are a later option. Exact schedules, hosting budgets, future projects' model choices, public visibility, and licenses have not been committed.

## Suggested first response from the continuing agent

Briefly confirm the checkout and explain: “EvidenceLens's local v1 implementation is present; real model selection and validation remain. We can continue that milestone after confirming your model/provider preference.”

Then follow the user's current request. Do not ask them to repeat context already captured here, restart the ten-project plan, or describe pending live AI acceptance as completed.
