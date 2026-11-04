# Verification of the first implementation slice

Run date: 5 November 2026, Asia/Karachi. These results describe this checkout and local environment, not unexecuted CI or a completed v1 release.

## Environment

- macOS, Node.js 22.11.0, npm 10.9.0, Python 3.12.14.
- Dedicated development and test databases on existing PostgreSQL 14.15. No existing application database/role was altered.
- Next.js 16.4.5, React 19.3.1, FastAPI 0.162.0, SQLAlchemy 2.1.8, Alembic 1.20.1, psycopg 3.3.8.
- No API keys or live model calls. Fixture mode only. The local PostgreSQL installation has no pgvector extension; no vector behavior is claimed tested.

## Passed

- **27 backend tests** against real PostgreSQL, through FastAPI's test client. This includes the complete fixture source/review/export flow; supported/conflicting/insufficient scenarios; honest custom-input failure; owner/collection/direct-ID checks; idempotency and stale review conflicts; explicit partial coverage; immediate deletion revocation and cleanup; queued/running cancellation and retry; expired-lease fencing; invalid quote rejection; upload limits/encoding/type checks; Host/Origin restrictions; pagination; preserved source bytes and checksum integrity; and the concurrent publication regression described below.
- **Alembic schema check:** no new upgrade operations detected after applying the committed initial migration to the dedicated test database.
- **TypeScript checks** and a **Next.js production build**, including generated source-response types.
- **OpenAPI generation:** emitted backend schema and generated frontend declarations; CI is configured to detect contract drift.
- **Real HTTP workflow through Next.js's API proxy:** sample creation → four separate worker ingestion jobs → PostgreSQL-backed investigation → exact source citation lookup → accepted review/note → reviewed Markdown response. An actual exported example is in [example-brief.md](example-brief.md).
- **Restart persistence:** API, worker, and frontend were stopped and restarted through the launcher; the existing investigation, findings, and accepted review revision remained available. Cleanup of the earlier smoke-test collection completed.
- **Frontend production dependency audit:** `npm audit --omit=dev --audit-level=high` reported zero known vulnerabilities.
- **Python dependency consistency:** `pip check` reported no broken requirements. PyPI release metadata listed zero advisories across the 28 locked packages at check time; see [python-advisories.json](python-advisories.json). This metadata check is not a complete security audit.

The backend test run emits one upstream warning: Starlette deprecates its httpx-based test client in favor of httpx2. The 27 tests pass; this warning is recorded rather than suppressed.

## Reproduced defect and fix

The initial real HTTP run caught a READ COMMITTED/identity-map timing issue: a response could contain a previously loaded investigation with no outcome alongside newly committed successful job state and findings. The investigation read now serializes against publication/deletion and refreshes the loaded run under that boundary. A deterministic regression publishes from a separate worker transaction between reads and verifies a consistent final response. The subsequent real HTTP workflow passed.

Final review also fixed and regression-tested these cases: deleting one source no longer cancels unrelated ingestion; a cancelled running ingestion recovered after lease expiry becomes retryable; failed deletion cleanup can be retried without restoring source access; and originals are preserved byte-for-byte with integrity verification before extraction.

## Blocked or not executed

- **Browser E2E, responsive screenshots, keyboard/visual accessibility:** Chrome launched under Playwright but the desktop sandbox aborted the browser before a page opened. The supplied `apps/web/e2e.mjs` did not complete. No screenshots or browser pass results are claimed. The frontend HTTP response was 200 and the production build passed, which do not substitute for browser acceptance.
- **Docker Compose clean install:** Docker's socket was not available in the initial environment. The Compose recipe was written but not executed; verification used dedicated databases on the installed PostgreSQL server. The application launcher was exercised locally.
- **Development hot reload in this sandbox:** the default Turbopack development server reported `unable to start FSEvent stream` after startup. Production build/start worked. The README therefore uses the verified `--production` launcher path; development file watching must be checked outside this sandbox.
- **GitHub Actions:** workflow supplied, not executed on GitHub. No remote or push exists.
- **Live providers, semantic retrieval/embeddings, model variability, numeric AI quality gates, performance percentiles, full dependency/license/secret scanning, and public deployment:** not executed and not release-accepted.

## Reproduce

Use the commands and dedicated-test-database guard in the root README. Start the app/worker before `npm run test:e2e`; use Playwright Chromium or set `PLAYWRIGHT_CHROMIUM_EXECUTABLE` to an available Chrome binary. Browser acceptance and the clean-install path remain required before declaring M0–M2 fully accepted.
