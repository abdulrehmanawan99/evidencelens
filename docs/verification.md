# Local v1 verification

Verified 5 November 2026, Asia/Karachi. This records executed local checks for the v1 candidate. Live model acceptance remains pending.

## Environment

macOS15.8.1 x86_64, Python3.12.14, bundled Node24.19.0, Next16.4.5, React19.3.1, PDF.js6.5.438, pypdf6.21.4, PostgreSQL17 and pgvector0.8.7. The source launcher used UI3001/API8001 and a synthetic browser database. Full Docker verification used separate UI3100/API8100/DB55433, a fresh external test volume, and a private test artifact directory. Other local processes and databases were left untouched.

## Executed checks

- **60 backend tests passed** in41.71s against actual PostgreSQL/pgvector. Coverage includes PDF pages/warnings/rejections, byte integrity, immutable versions/restoration, hybrid retrieval and profile reindexing, scoped/direct-ID access, exact citations, claim revisions, review/export snapshots, cancellation, heartbeat/lease recovery, provider budgets/refusal/schema repair, cleanup/orphans, and excluded-source metadata deletion.
- **Alembic upgrade and schema check passed:** no new upgrade operations detected. Both an empty database and a copy of the previous application database were migrated. A private pre-upgrade SQL backup is retained in ignored .local/backups/pre-v1-backup.sql.
- **OpenAPI generation/drift and TypeScript checks passed.** The final source and Docker production builds passed with the pinned lockfiles.
- **Text and PDF browser workflows passed** on both source-run services and the full Docker stack. Tests cover ingestion, known conflict, exact source navigation, accepted review, saved Markdown download, reload persistence, insufficient evidence, hostile text rendering, PDF canvas pixels, suggestions requiring confirmation, page navigation, replacement/retained-version activation, mobile overflow, and keyboard tabs.
- **Automated accessibility scans passed with zero violations** for the representative evidence board and mobile PDF reader, using axe WCAG2A/AA and2.1AA tags. This is a bounded automated scan, not comprehensive accessibility certification. Actual desktop/mobile screenshots were captured and visually inspected.
- **Fresh full Docker installation passed:** database initialization/vector extension, migrations, unprivileged API/worker/web, read-only app filesystems, capability restrictions, ready health check, PDF extraction, browser review/export, and the six-case fixture suite. No provider credentials or Docker socket enter the parser/app images.
- **Container restart persistence passed:** a confirmed claim, accepted finding/note, and saved export checksum survived API/worker/UI restart. The temporary verification collection was then deleted.
- **Dependency checks passed:** pip check found no broken requirements; pip-audit2.10.1 found no known advisories in33 pinned Python runtime/development packages; npm audit found zero vulnerabilities across the locked frontend dependency graph. Bandit1.9.4 reported zero medium/high findings. The narrow tmpfs-path suppression is explained inline; reviewed low-level subprocess use supplies argument arrays without a shell.
- **Secret-pattern scan passed** over staged/tracked text with no matches. It checks common private-key/OpenAI/GitHub/AWS forms without printing values; it is not a guarantee that all possible secret formats are detected. Runtime files, .env, backups, originals, and build/dependency directories are ignored.
- **License inventory generated:**33 Python distributions and109 npm lock entries, including optional platforms. Dependency notices remain with their distributions; no project-wide license has been chosen.

The backend suite emits one upstream Starlette warning about its deprecated httpx-based test client; it is recorded rather than hidden.

## Continuation: evaluation quotation regression

The evaluation script previously gave expected-evidence credit when a labeled
fact appeared anywhere in the cited passage, even if the returned quotation was
an unrelated part of it. Scoring now requires the labeled text within the actual
valid quotation and the expected relation; retrieval recall remains separate.
Four offline regression tests passed, and a fresh six-case text/PDF fixture run
passed all expected outcomes and citation checks with full labeled retrieval and
quotation evidence recall. Its report is retained locally as
`.local/evaluation-quote-fix.json`; historical reports were not overwritten.
These are still fixture results, not live model acceptance.

## Measured fixture results

[evaluation-fixture.json](evaluation-fixture.json) and [evaluation-docker.json](evaluation-docker.json) each passed six cases: three known claims against text and PDF versions. Both record6/6 expected outcomes, six exact citations, all six cases passing citation validation, and1.0 labeled passage/evidence recall within context. These are predefined synthetic regression scenarios; they do not measure live semantic model quality or generalization.

The source-run investigation median/max were655.5/906ms; the Docker suite median/max were632/902ms. These include API polling and a single worker.

[performance-fixture.json](performance-fixture.json) separately measured eight warm text investigations per concurrency, with one FIFO worker and100ms polling. At concurrency1 the end-to-end median/p95 were722/1017ms and queue median/p95 were431/514ms. At concurrency4 they were941/1184ms and593.5/980ms. With n=8, p95 is the maximum. This tiny fixture workload does not establish large-PDF, live-provider, endurance, or production capacity. [resources-local.json](resources-local.json) is a post-benchmark startup/readiness snapshot, not peak or steady-state resource usage.

The human-labeled new-source split in fixtures/evaluation.json covers five additional support/conflict/unanswerable/period/injection cases. It has not been scored with a live model.

## Defects reproduced and corrected

Verification exposed overly restrictive AND keyword matching, low-contrast labels, a CSS class collision in the context group, inactive-tab keyboard navigation, PDF blank-page selection, completed-job polling, retained-version recovery access, and stale excluded-source filenames in export snapshots. The implementation and relevant regression checks were updated. Source deletion now purges snapshots whether a removed source was included or explicitly excluded from the investigation.

## Reproduce browser verification

Use the source commands in README, or run the full Docker stack. On Docker Desktop, the browser harness can reach the full app's configured loopback origin through an internal test-only proxy:

```bash
docker run --rm --memory 1536m --cpus 2 --pids-limit 256 --shm-size 256m \
  --cap-drop ALL --security-opt no-new-privileges \
  -v "$PWD:/app:ro" -v "$PWD/docs/screenshots:/app/docs/screenshots:rw" \
  -w /app/apps/web -e E2E_PROXY_PORT=3000 -e E2E_ACCESSIBILITY=1 -e E2E_EXTENDED=1 \
  mcr.microsoft.com/playwright:v1.64.1-noble@sha256:2f05f8a734509a7b3f26a912639488ee08f58a7b292d14d62271bcff9038768f \
  node e2e-container.mjs
```

Tests create/delete their own synthetic collections. Screenshots in screenshots/ are real captures, not mockups. example-brief.md was produced through a saved reviewed PDF export; its temporary source collection was removed afterward.

## Fresh-clone check — 10 November 2026

The `chore/complete-v1` branch was cloned from GitHub into an empty directory and the
README Docker quick start was followed with port and name overrides (`APP_PORT=3020`,
`API_PORT=8020`, `DB_PORT=55440`, plus `COMPOSE_PROJECT_NAME`, `PGDATA_VOLUME` and
`DB_CONTAINER_NAME`) because another copy was already running on the defaults.

- `scripts/setup-local.py` and `docker compose --profile app up --build -d` succeeded;
  API health reported ready in fixture mode.
- The PDF sample workflow through the UI's API proxy reached 4/4 ready sources,
  returned `conflicting_evidence` with three findings, accepted all three, and saved
  a reviewed export containing all three exact quotations (this run used the since-reverted v5 version; fixture
  results do not depend on it).
- The Docker Playwright harness above (`E2E_EXTENDED=1`, accessibility on) passed both
  the text and PDF browser workflows with zero axe violations; the screenshots in
  `docs/screenshots/` were retaken from this run.
- `scripts/evaluate.py --suite fixture` passed 6/6 cases with exact citations and 1.0
  evidence recall; 83 backend tests passed on that instance's disposable
  `evidencelens_test_local` database; frontend typecheck and production build passed.

The clone's containers, volume and images were removed afterwards.

## Outstanding acceptance

The checks above are fixture or mocked verification. Live generation has been tested
only with `gemini-3.5-flash-lite` on synthetic samples with `local_lexical` retrieval;
an experimental v5 analysis returned HTTP 400 in its single live check and was reverted to v2. [Live
validation](live-validation.md) and [evaluation-live.json](evaluation-live.json) record
the exact call counts, results and limits. No hosted embedding, alternate model,
held-out result or full AI acceptance is claimed. CI on GitHub Actions is the record
for each commit.
