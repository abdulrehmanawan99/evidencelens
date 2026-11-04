# Local prototype threat model

Status: implemented-boundary review for the M0–M2 text/fixture slice. This is not a security certification or hosted deployment approval.

## Assets and trust

Assets are uploaded source text, its derived passages/quotes, analyst claims and notes, local database state, and exported briefs. The logged-in OS user controls the installation and trusted configuration. Uploaded documents and returned content are untrusted. There is no live provider/key handling yet.

Local loopback reachability is not account authentication. A malicious local process, OS compromise, browser extension, or another user with access to these files can defeat the local boundary. Do not expose either application port outside loopback.

## Controls in this slice

- **Cross-collection/direct-ID disclosure:** scoped owner/collection lookup before source, job, run, review, or export access; composite foreign keys for evidence relationships. Tests inject a second owner only through test dependency overrides. There is no runtime owner impersonation header.
- **Cross-site writes and DNS rebinding:** allowed Host names, exact Origin allowlist, same-origin requests, rejected `Sec-Fetch-Site: cross-site`, no wildcard CORS, and loopback-only startup commands/Compose port publication.
- **Oversized or hostile uploads:** raw streamed byte cap; UTF-8/null/empty checks; finite document and decoded-character limits; random storage keys independent of original filenames. PDF and binary formats are rejected, avoiding a parser surface not yet isolated.
- **Stored XSS:** React text rendering; no imported HTML insertion; source/model text is never used as executable code. Security headers disable frames/objects and restrict connections to the same origin. Next.js requires inline runtime/style allowances in this prototype; its CSP is not represented as maximally strict.
- **Prompt injection:** fixture adapter has no tools or network access and only accepts known corpus checksums. This does not prove resistance of a future live model; injection evaluation must be repeated after provider integration.
- **Stale/duplicate work:** leases, fencing tokens, limited attempts/deadlines, cancellation checks, and transactional publication. Stale review writes and idempotency-key input mismatches return conflicts.
- **Deletion:** immediate tombstone/access revocation and invalidated exports, followed by worker cleanup of originals, passages, source-linked findings, and review text. Late worker publication checks prevent resurrection.
- **Secrets/data in Git:** ignored `.env`, `.local`, caches, and dependency/build directories; original fixtures are synthetic and contain no confidential source material. Known development database credentials are examples, not live secrets. Runtime originals are never a static web directory.

## Review findings and fixes

- **Source injection through citation data:** the worker validates passage collection, pinned source manifest, exact quote offsets, and quote equality before publication. An invented-quote test verifies rejection before any finding is persisted.
- **Late worker publication:** publication requires the current unexpired token; a lease-reclaim test proves the prior worker cannot publish.
- **Deletion race:** source access is revoked before asynchronous cleanup and existing exports are invalidated; cancellation and lease checks prevent reintroducing data.
- **Review overwrite:** an expected revision is required; repeat stale writes return `409` and append-only review events preserve changes.

## Remaining release work and limits

Browser interaction, visual accessibility, and rendering behavior remain unverified in this environment because Chrome could not launch. The browser test includes a hostile text-rendering check but has not completed. Dependency audit results and actual test commands are in `verification.md`.

The Docker recipe and GitHub workflow are supplied but unexecuted here. Containers/images, action pinning, parser isolation, live-provider data handling, prompt injection, embedding scope/recall, storage quotas across all resources, backup retention, log retention, crash-orphan sweeping, and load behavior need later acceptance. A crash after original-file creation can leave an orphan; deletion jobs are bounded and can fail after their retry/deadline window. Operators can inspect job status and use `POST /api/v1/jobs/{id}/retry-cleanup` to retry failed deletion without restoring access; this prototype does not claim guaranteed erasure.

Changing `DATABASE_URL` points at another database; use a dedicated application database and role. Tests refuse database names outside `evidencelens_test_*`, but that naming guard does not replace operator care. App deletion cannot recall downloaded Markdown or user backups. Public deployment requires real authentication, CSRF/session policy, per-user/workspace authorization, hardened runtime roles, and a separate security review.
