# EvidenceLens

A local reading room for checking a claim against a set of PDF or text reports. EvidenceLens finds the passages that support, contradict or qualify the claim, links every finding to the exact quoted text, lets you accept or dismiss each one, and exports a cited Markdown brief.

## Problem and user

Analysts, researchers and editors often receive several reports that disagree: a preliminary estimate, a final figure, a board summary with a different number. Checking a single claim means reading all of them and copying quotes by hand. EvidenceLens is for one person on their own machine who needs to answer "what do my sources actually say about this claim?" with exact citations, and who wants a human review step before anything is written down.

Everything runs locally (PostgreSQL + pgvector, FastAPI, Next.js). A built-in fixture mode demonstrates the full workflow with synthetic reports and no model key. A live mode sends selected passages to a model you configure.

## Features

- PDF and UTF-8 text ingestion with page/line references, checksums and extraction warnings; originals are kept unchanged.
- Source versions: replace a source, read or restore retained versions; results that depend on changed sources are marked stale.
- Hybrid keyword + vector retrieval over pgvector, with a visible retrieval trace for every run.
- Claim investigation with outcomes `supported_in_sources`, `conflicting_evidence`, `insufficient_evidence` or `uncertain`. Findings are labelled supporting, conflicting or context, and every quote is checked against the stored passage text.
- Accept/dismiss each finding with notes and history, then export a reviewed (or labelled draft) Markdown brief with frozen provenance.
- Live generation through OpenAI, any OpenAI-compatible chat API (for example Gemini), or Ollama. Keys stay in server-side `.env`, never in the browser.
- Responsive interface with a PDF canvas reader, keyboard-navigable tabs and automated accessibility checks.

## Screenshots

Desktop evidence board after investigating the sample claim and accepting a finding:

![Desktop evidence board](docs/screenshots/evidence-board.png)

Mobile reading room (390 px wide):

<img src="docs/screenshots/mobile-reading-room.png" alt="Mobile reading room" width="320">

## Quick start (fixture mode, no key)

Requirements: Docker Desktop (or Docker Engine with Compose v2) and Python 3.

```bash
git clone https://github.com/abdulrehmanawan99/evidencelens.git
cd evidencelens
python3 scripts/setup-local.py
docker compose --profile app up --build -d
```

The setup helper creates a private `.env` from `.env.example`, a local artifact directory (`.local/v1-artifacts`) and the Docker volume `evidencelens_v1_pgdata`. The first build takes a few minutes.

Open <http://127.0.0.1:3000>, then:

1. Choose **Open PDF sample** and wait for "4 of 4 sources ready".
2. Choose **Investigate claim** to check the default claim. Fixture mode reports conflicting evidence with three findings.
3. Choose **Read in source** on a finding to see the exact highlighted passage in the PDF.
4. **Accept** the findings you agree with, then choose **Export reviewed brief** to download the Markdown brief.

Stop with `docker compose --profile app stop`. Data persists in the volume and `.local/v1-artifacts`. To remove everything: `docker compose --profile app down`, then `docker volume rm evidencelens_v1_pgdata` and delete `.local/`.

Only loopback ports are published: 3000 (UI), 8000 (API), 55432 (database). App containers run as your user, with read-only filesystems, no Linux capabilities and memory limits.

**Different ports or a second copy.** Before running setup, create `.env` from `.env.example` and add overrides, for example:

```dotenv
APP_PORT=3020
API_PORT=8020
DB_PORT=55440
COMPOSE_PROJECT_NAME=evidencelens-second
PGDATA_VOLUME=evidencelens_second_pgdata
DB_CONTAINER_NAME=evidencelens-second-db
```

Then run the two commands above. Never point two installations at the same artifact directory or database volume.

### Run from source instead

Requires Python 3.12, Node.js 22.13+ (24 recommended) and Docker for the database (or PostgreSQL 17 with pgvector).

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements-dev.lock
npm ci --prefix apps/web
python3 scripts/setup-local.py
docker compose up -d db
.venv/bin/python scripts/run-local.py --production
```

The launcher reads `.env`, migrates the database, builds the UI and starts the API, worker and UI; Ctrl+C stops them. Use `--port 3001 --api-port 8001` if the default ports are busy, and set `NODE_EXECUTABLE` if your Node binary is not on PATH. On macOS, source runs parse PDFs inside a small Docker container; on Linux they use a resource-limited subprocess. Do not run the source launcher and the app containers against the same database.

## Use your own Gemini key

This uses Gemini for generation and the built-in `local_lexical` retrieval profile, so no embedding API is called. It is the only live configuration that has been tested (see [Limitations](#limitations)).

1. Create an API key in [Google AI Studio](https://aistudio.google.com/apikey). The free tier is enough for a few test investigations.
2. Open the `.env` file created by setup (it is git-ignored and readable only by you) and add or replace these lines:

   ```dotenv
   MODEL_MODE=openai_compatible
   GENERATION_MODEL=gemini-3.5-flash-lite
   GENERATION_ENDPOINT=https://generativelanguage.googleapis.com/v1beta/openai
   GENERATION_API_KEY=paste-your-key-here
   EMBEDDING_PROVIDER=local_lexical
   EMBEDDING_MODEL=hashed-lexical-demo-v1
   EMBEDDING_ENDPOINT=local
   EMBEDDING_DIMENSIONS=64
   EMBEDDING_API_KEY=
   CONTEXT_TOKENS=16000
   ```

3. Restart so the API and worker read the new settings: `docker compose --profile app up -d` (Docker) or stop and rerun `run-local.py` (source).
4. Reload the UI. The provider bar should say "Live model configuration" and show `gemini-3.5-flash-lite` with `retrieval: local_lexical`. Choose **Check provider** (one generation request).
5. For collections created before the switch, choose **Rebuild search index**. New collections are indexed automatically.
6. Start with the synthetic samples. Live mode sends the claim and selected source passages to Google; do not upload documents you are not allowed to share with that service.

To go back to fixture mode, set `MODEL_MODE=fixture` and restart.

### Other OpenAI-compatible providers

The same adapter works with any provider that offers `/chat/completions` with strict JSON-schema `response_format` (and, for embeddings, an OpenAI-style `/embeddings` endpoint). Set:

```dotenv
MODEL_MODE=openai_compatible        # or openai for the OpenAI Responses API, or ollama
GENERATION_MODEL=provider-model-id
GENERATION_ENDPOINT=https://provider.example/v1
GENERATION_API_KEY=your-key
# Keep EMBEDDING_PROVIDER=local_lexical, or use hosted embeddings:
EMBEDDING_PROVIDER=openai_compatible
EMBEDDING_MODEL=provider-embedding-id
EMBEDDING_ENDPOINT=https://provider.example/v1
EMBEDDING_API_KEY=your-key
EMBEDDING_DIMENSIONS=1536           # the model's real output size
```

For Ollama, use `ollama` for both settings and the endpoint `http://127.0.0.1:11434` (source run) or `http://host.docker.internal:11434` (Docker). Endpoints must be HTTPS except for loopback/local hosts. **Check provider** verifies the contract; it does not prove output quality. Details: [provider setup](docs/providers.md).

## Tests

Backend tests delete application rows, so they must use a disposable database whose name starts with `evidencelens_test_`. The Docker database creates `evidencelens_test_local` for this.

```bash
docker compose up -d db
export TEST_DATABASE_URL=postgresql+psycopg://evidencelens:evidencelens_local@127.0.0.1:55432/evidencelens_test_local
cd backend
DATABASE_URL="$TEST_DATABASE_URL" ../.venv/bin/python -m alembic upgrade head
../.venv/bin/python -m pytest -q
cd ..
.venv/bin/python -m unittest discover -s scripts -p test_evaluate.py

cd apps/web
npm run typecheck && npm run build
```

With the app running in fixture mode:

```bash
# Six-case fixture evaluation through the public API (creates and deletes its own collections)
.venv/bin/python scripts/evaluate.py --api http://127.0.0.1:8000 --suite fixture --output .local/evaluation-fixture.json
# Browser workflows (also rewrite docs/screenshots)
cd apps/web && npx playwright install chromium
E2E_BASE_URL=http://127.0.0.1:3000 E2E_ACCESSIBILITY=1 npm run test:e2e
E2E_BASE_URL=http://127.0.0.1:3000 E2E_ACCESSIBILITY=1 node e2e-pdf.mjs
```

A Dockerised Playwright harness that needs no local browser is in [verification](docs/verification.md#reproduce-browser-verification). GitHub Actions runs all of the above on every pull request.

## Limitations

- **Live AI quality is not established.** Live generation was tested only with `gemini-3.5-flash-lite` on a few synthetic samples, using lexical (not semantic) retrieval. Earlier analysis versions produced correct outcomes and exact quotes on three text cases but missed one expected context quote. An experimental `grounded-evidence-v5` version was rejected by Gemini with HTTP 400 and has been reverted; the app uses `grounded-evidence-v2`, which completed live requests with HTTP 200. Live PDF investigations were only partially exercised. See [live validation](docs/live-validation.md).
- Fixture mode answers only the three bundled sample claims. Its results are predefined and do not measure model quality.
- `local_lexical` retrieval is word-count hashing, not semantic search.
- Scanned PDFs without a text layer are rejected (no OCR). PDF reading order can differ from the visual layout.
- Limits: 20 MiB per file, 100 PDF pages, 500,000 extracted characters per file, 25 sources and 100 MiB per collection, 10 retained versions per source.
- Single-user local installation: there are no accounts, and the app is not meant to be exposed beyond `127.0.0.1`. Downloaded briefs and backups are outside the app's control once saved.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `external volume "evidencelens_v1_pgdata" not found` | Run `python3 scripts/setup-local.py` first; it creates the volume. |
| `port is already allocated` / address in use | Set `APP_PORT`, `API_PORT`, `DB_PORT` in `.env` and run `docker compose --profile app up -d` again. |
| `container name "/evidencelens-v1-db" is already in use` | Another copy is running. Set `COMPOSE_PROJECT_NAME`, `DB_CONTAINER_NAME` and `PGDATA_VOLUME` as shown above. |
| Provider bar says "Configuration incomplete" | A setting is missing or invalid (for example an `http://` remote endpoint, a missing model ID or wrong embedding dimensions). Fix `.env` and restart. |
| Investigation fails with `provider_request_rejected` | The provider returned HTTP 4xx for the request. With the current analysis version this is the known Gemini HTTP 400 described under Limitations. |
| `provider_rate_limited` or `provider_authentication_failed` | Quota exhausted or key invalid. The app stops after one request and does not retry. |
| Investigating your own claim fails in fixture mode | Fixture mode only knows the three sample claims (listed under "Sample claims supported in fixture mode"); use a live provider for other claims. |
| PDF upload rejected as having no text | The PDF is a scan; OCR is not supported. |
| Next.js warns about Rosetta on Apple Silicon | Harmless; it means an x86-64 Node binary is installed. |

API documentation is served at <http://127.0.0.1:8000/docs> while the app runs.

## Documentation

- [Architecture](docs/architecture.md)
- [Provider setup and evaluation](docs/providers.md)
- [Live validation results](docs/live-validation.md)
- [Verification record](docs/verification.md)
- [Threat model and retention](docs/threat-model.md)
- [Implementation status](docs/status.md)
- [Release checks](docs/release-checks.md) and [release notes](docs/release-notes.md)
- [Example exported brief](docs/example-brief.md)
- [Dependency/license inventory](docs/licenses.json)
