# EvidenceLens

A private, local PDF/text reading room for investigating claims, comparing conflicting reports, reviewing exact source citations, and saving cited Markdown briefs.

**Local v1 functionality is implemented. Live AI acceptance is pending a configured provider.** Fixture mode is a reproducible demonstration with synthetic reports and predefined interpretations; its results do not establish model quality.

![Evidence board](docs/screenshots/evidence-board.png)

## Included

- PDF and UTF-8 text ingestion, preserved originals, page/line references, checksums, extraction warnings, and durable cancellable jobs.
- Immutable source versions, replacement, retained-version reading/restoration, stale-result invalidation, retries, and deletion of derived artifacts.
- PostgreSQL/pgvector hybrid retrieval, versioned embedding profiles, explicit reindexing, retrieval traces, and bounded context.
- Server-configured OpenAI Responses, OpenAI-compatible chat, and Ollama adapters; separate generation/embedding settings, capability checks, structured output validation, and provider usage/error traces.
- Confirmed claims and revisions, optional claim suggestions, supporting/conflicting/context evidence, uncertainty, and insufficient-evidence outcomes.
- Review decisions and notes with revision checks, history, persisted draft/reviewed exports, frozen provenance, and guarded downloads.
- Responsive editorial interface, keyboard tabs, same-origin PDF worker/assets, and automated accessibility/browser checks.

## Start with Docker

Use Docker Desktop/Compose and Python 3 for the setup helper. Run from this project directory:

```bash
python3 scripts/setup-local.py
docker compose --profile app up --build -d
```

Open [the local app](http://127.0.0.1:3000). Choose **Open PDF sample**, wait for four ready sources, investigate the default claim, open each citation, accept evidence, and export a reviewed brief. Fixture mode needs no model key.

Only loopback ports 3000 (UI), 8000 (API), and 55432 (database) are published. The API migrates before the worker/UI start. App containers run without root, with read-only filesystems and bounded memory. No Docker socket is mounted into them.

Stop with `docker compose --profile app stop`. Database volume `evidencelens_v1_pgdata` and private originals in `.local/v1-artifacts` persist. To use different ports set `APP_PORT`, `API_PORT`, and `DB_PORT` in ignored `.env`, then recreate containers. Never point two independent installations at the same artifact directory.

## Run from source

Requires Python 3.12, Node.js 22.13+ (24 recommended), npm, and PostgreSQL 17 with pgvector. On macOS, Docker also isolates PDF parsing. On Linux, parsing uses a subprocess with resource limits.

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements-dev.lock
npm ci --prefix apps/web
python3 scripts/setup-local.py
docker compose up -d db
.venv/bin/python scripts/run-local.py --production
```

The launcher reads ignored `.env`, migrates the database, prepares local PDF assets, builds the UI, and starts the API, worker, and UI. Ctrl+C stops its own children. It refuses occupied ports; use `--port 3001 --api-port 8001` for another instance. Set `NODE_EXECUTABLE` if your supported Node binary is outside PATH. For development, omit `--production`.

Do not mix a source launcher and full app containers on the same database/ports. Existing PostgreSQL installations need the vector extension installed by an administrator; application migrations intentionally do not escalate privileges.

## Configure live models

All settings belong in ignored server-side `.env`; no keys are entered in the browser or committed to Git. Fixture is the default.

```dotenv
MODEL_MODE=openai
GENERATION_MODEL=your-structured-output-model
GENERATION_ENDPOINT=https://api.openai.com/v1
OPENAI_API_KEY=your-private-key
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_ENDPOINT=https://api.openai.com/v1
EMBEDDING_DIMENSIONS=1536
CONTEXT_TOKENS=16000
```

Separate `GENERATION_API_KEY` and `EMBEDDING_API_KEY` override `OPENAI_API_KEY`. For compatible APIs use `MODEL_MODE=openai_compatible` and/or `EMBEDDING_PROVIDER=openai_compatible`. They must support strict JSON schema and the embedding request contract. For Ollama use `ollama`, set both model IDs and actual embedding dimensions, and use endpoints such as `http://127.0.0.1:11434` (source run) or `http://host.docker.internal:11434` (Docker).

Restart API/worker after configuration changes. Choose **Check provider**, then **Rebuild search index** for existing sources. A configured provider is not a quality guarantee. Live mode sends selected document excerpts and claims to the configured services. Fixture mode makes no model calls. See [provider setup and evaluation](docs/providers.md).

## Verify

Tests require a disposable database named `evidencelens_test_*`; they delete its application rows. The database initializer supplies `evidencelens_test_local`.

```bash
export TEST_DATABASE_URL=postgresql+psycopg://evidencelens:evidencelens_local@127.0.0.1:55432/evidencelens_test_local
cd backend
DATABASE_URL="$TEST_DATABASE_URL" ../.venv/bin/python -m alembic upgrade head
../.venv/bin/python -m pytest -q --basetemp=../.local/test-run
cd ../apps/web
npm run typecheck
npm run build
npx playwright install --with-deps chromium
E2E_ACCESSIBILITY=1 npm run test:e2e
E2E_ACCESSIBILITY=1 node e2e-pdf.mjs
```

Browser tests require the app and worker running. They create/delete only their own collections and save actual screenshots. The Docker browser harness and measured results are documented in [verification](docs/verification.md). CI is supplied; no GitHub Actions run is claimed until this repo is pushed.

```bash
.venv/bin/python scripts/evaluate.py --suite fixture --output docs/evaluation-fixture.json
.venv/bin/python scripts/evaluate.py --suite live --output docs/evaluation-live.json
.venv/bin/python scripts/benchmark.py --output docs/performance-fixture.json
```

The live command exits with status 2 and records blocked coverage when fixture mode is active. A small fixture benchmark measures this workload only.

## Contracts and limits

[Local API docs](http://127.0.0.1:8000/docs) describe endpoints. Regenerate frontend contracts with `.venv/bin/python scripts/export-openapi.py` and `npm run api:generate --prefix apps/web`.

Uploads use a streamed raw body with `X-Filename` and a PDF/text Content-Type. Limits: 20 MiB/file, 100 PDF pages, 500,000 extracted characters/file, 25 source families/collection, 10 retained versions/source, 100 MiB retained source bytes/collection, 5,000 active passages, 50 pending jobs/collection, two concurrent investigations/collection, and 100 exports/collection. PDF scans require OCR and are rejected when no text is extractable; OCR is outside v1. Reading order can differ from the visual PDF layout. Parser memory, decoded content, time, model output, calls, context, and retries are bounded.

Local access belongs to one OS-controlled installation. There are no hosted accounts or public access controls. Deletion revokes access immediately, then a worker removes originals and derived content; downloaded briefs and backups remain outside app control.

## Project records

- [Implementation status](docs/status.md)
- [Architecture](docs/architecture.md)
- [Threat model and retention](docs/threat-model.md)
- [Verification and remaining acceptance](docs/verification.md)
- [Release notes](docs/release-notes.md)
- [Dependency/license inventory](docs/licenses.json)

The repository is on the Desktop. No GitHub publication, hosting, or project-wide open-source license grant is implied.
