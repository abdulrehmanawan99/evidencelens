# EvidenceLens

A private document reading room for investigating a claim across reports, reviewing source-linked evidence, and exporting a cited brief.

**Current state: the M0–M2 text/fixture vertical slice.** This is runnable software with PostgreSQL persistence and a separate worker. It is not the completed v1 release. PDF ingestion, embeddings/vector retrieval, and live model providers are not connected yet.

## What works

- Create independent collections and load four original synthetic Harbor Transit reports.
- Upload UTF-8 `.txt` files, read immutable passages with line references, and track durable ingestion jobs.
- Investigate the three displayed sample claims using an explicitly labeled fixture provider. Unsupported claims or custom sources return `fixture_not_available`, rather than canned analysis.
- Compare support, candidate conflict, and provisional context; open exact cited passages.
- Accept/dismiss findings, save reviewer notes, preserve decisions across restart, and export reviewed or explicitly labeled draft Markdown.
- Cancel ingestion/investigation jobs, retry cancelled/failed ingestion, recover expired worker leases, and remove sources with immediate access revocation and background cleanup.
- Keep collections, jobs, sources, and results scoped to a server-assigned local owner. This is a local access boundary, not hosted account authentication.

The editorial interface uses a collection library, a claim desk, an evidence board, and a line-referenced source reader. Browser screenshots are pending because the current desktop sandbox prevented Chrome from launching; none are fabricated.

## Run locally

Prerequisites: Python 3.12+, Node.js 22.11+, npm, and PostgreSQL 14+ (or Docker Compose). Use `127.0.0.1`, not a public interface. The default development credentials are deliberately public examples; never use this configuration for hosting.

From the repository root:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.lock
npm ci --prefix apps/web
cp .env.example .env
docker compose up -d db
.venv/bin/python scripts/run-local.py --production
```

Open [EvidenceLens locally](http://127.0.0.1:3000) and choose **Open sample collection**. Wait until all four sources are ready, then select **Investigate claim**. Accept a finding to enable the reviewed export. The provider requires no API key and makes no model network calls.

The launcher applies migrations and starts the API, worker, and UI. Ctrl+C stops its child processes. `--production` builds and starts the verified production UI; omit it for development hot reload. The current desktop sandbox blocks Turbopack's macOS file watcher, so use production mode in this environment. The launcher does not stop the database; use `docker compose stop db` when finished. Volumes retain work. Do not run `docker compose down -v` unless you intend to erase the local database.

If PostgreSQL is already installed, create dedicated application and test databases, put its application DSN in `.env`, and omit the Docker command. The role needs ownership of the application's schema/tables for migrations, not PostgreSQL superuser privileges. `.env` values can be overridden by exported environment variables. No existing databases or roles need to be changed.

## Verify

Use a dedicated test database whose name starts with `evidencelens_test_`. The test suite resets all application tables in that database and refuses other database names. The Compose initializer supplies `evidencelens_test_local`.

```bash
export TEST_DATABASE_URL=postgresql+psycopg://evidencelens:evidencelens_local@127.0.0.1:55432/evidencelens_test_local
cd backend
DATABASE_URL="$TEST_DATABASE_URL" ../.venv/bin/python -m alembic upgrade head
../.venv/bin/python -m pytest -q
cd ../apps/web
npm run typecheck
npm run build
```

With the API, worker, and UI running against a development database:

```bash
cd apps/web
npx playwright install chromium
npm run test:e2e
```

For an installed Chrome, set `PLAYWRIGHT_CHROMIUM_EXECUTABLE` to its executable instead of downloading a test browser. The browser test creates and deletes only its own collection; it saves real screenshots in `docs/screenshots/`. See [verification report](docs/verification.md) for checks actually executed. The GitHub Actions workflow is supplied but has not run on GitHub until a repository is created and pushed.

## API contracts

Interactive API docs are at [local FastAPI docs](http://127.0.0.1:8000/docs). Frontend response types are generated from OpenAPI. To update them:

```bash
.venv/bin/python scripts/export-openapi.py
cd apps/web
npm run api:generate
```

CI checks for drift. File upload uses a **raw streamed text body** with `X-Filename: encoded-name.txt` and `Content-Type: text/plain`, rather than multipart. It applies the byte cap while receiving data; this first slice is limited to 2 MiB and 500,000 decoded characters per file, with 25 files per collection. Lists are bounded; collections and investigation history have cursor pagination.

## Boundaries and next work

- Fixture mode supports only the bundled reports and three displayed claim scenarios. Custom text ingestion/reading works, but arbitrary AI analysis does not.
- Current exports are generated from a locked review/source snapshot in a bounded request. Persistent export artifacts/jobs, source replacement/version management, full claim lifecycle, and full evaluation reporting are later milestones.
- No account UI, arbitrary endpoint configuration, provider keys, public links, cloud infrastructure, GitHub remote, or deployment is configured.
- The local prototype uses PostgreSQL without requiring pgvector. The vector schema/index/profile contract belongs to M4 and must be tested with actual embeddings before acceptance.
- A pending job has a 180-second execution/recovery window from creation and up to three attempts. The current fixture/text tasks are bounded and short; long parsing/model tasks require renewed leases, separate limits, and more detailed stage checkpoints in later milestones.
- Source deletion revokes access first; the worker then deletes stored text, passages, linked findings, and review text. Prior investigations become stale and cannot export. Deletion cannot recall downloaded briefs or local backups.

See [architecture](docs/architecture.md), [threat model](docs/threat-model.md), and [implementation status](docs/status.md). Source and sample code are not licensed for public redistribution yet; choose a repository license before publication. No GitHub publication has been performed.

## Troubleshooting

- **Database not ready:** verify the DSN, database service, role access, and `alembic upgrade head`.
- **Sources remain queued:** run the worker with the same `DATABASE_URL` and `STORAGE_DIR` as the API. Jobs which miss their deadline show a failed state; retry ingestion or start another investigation.
- **Origin rejected:** use `http://127.0.0.1:3000`; update `APP_ORIGIN` if deliberately changing the local origin. Wildcard CORS is intentionally absent.
- **Fixture unavailable:** use the original sample collection and one of the three displayed sample claims. A custom document changes the supported fixture corpus.
- **Stale investigation/export conflict:** the source collection or review revision changed. Start a fresh investigation or reload the current review.
- **Upload rejected:** the current build accepts only non-empty UTF-8 `.txt` files, within the documented limits. PDF support has not shipped.
