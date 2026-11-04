# Local v1 threat model

This is an implementation review for one private OS-controlled installation. It is not a hosted deployment approval or security certification.

## Trust and assets

Private assets include uploaded originals, extracted text, vectors, claims, notes, model interpretations, provider credentials, and exports. The OS user controls server configuration. Documents and model output are untrusted. Loopback access is not account authentication: local processes, extensions, shared-machine users with file access, and OS compromise remain outside the app boundary.

## Implemented controls

- Record-ID routes check the owning collection; vector/keyword retrieval is scoped to pinned source IDs. Composite evidence references and exact quote/context validation prevent invented or cross-collection citations.
- Exact Origin/Host policies, rejected cross-site fetches, no permissive CORS, same-origin proxying, and loopback published ports reduce browser cross-site and rebinding exposure.
- Raw streamed uploads have byte/time/type limits; random storage keys never derive paths from filenames. Family/version/storage/page/text/passage/job/export quotas bound local work.
- PDF parsing uses a secret-free child and resource limits. macOS's dedicated parser container has no network, read-only single input, no privileges/capabilities,512MiB memory, one CPU,32 processes,16MiB tmpfs, and a wall deadline. Linux subprocesses run inside the app container in Docker; source-run Linux isolation is weaker than a dedicated network namespace.
- React renders source/model text as text. PDF.js uses same-origin assets, no annotation actions, disabled XFA/Wasm, and bounded pixels/images. CSP forbids external connections/objects/frames and unsafe-eval; inline Next runtime/style allowances remain.
- Models have no tools. The prompt treats source instructions as data. IDs, exact quote offsets, relations/outcomes, structured schema, refusals, vector dimensions/norms, context/call/response limits, and one repair are enforced deterministically. This does not prove semantic prompt-injection resistance.
- HTTP adapters use bounded response streaming, timeout/retries/deadlines, no redirects or environment proxies, and trusted server endpoint configuration. Keys remain in ignored server configuration and are excluded from parser environments, browser responses, screenshots, and logs. Full app Docker images exclude .env and runtime artifacts.
- Lease fencing, renewed leases, cancellation, collection revisions, optimistic reviews, and locked snapshots protect against stale/duplicate publication.

## Retention and deletion

Deleting a source revokes all its versions immediately and invalidates prior analyses/exports. Worker cleanup removes original files, passages, vectors, retrieval hits, source-dependent findings/notes/review events, suggestion payloads, and saved export snapshots/files. Deleting a collection also clears analyst claim text/revisions. Manual claims remain when only a source is deleted.

Tombstone IDs, checksums, numeric usage/timing, model configuration, and job events may remain in PostgreSQL. Cleanup can fail; POST /api/v1/jobs/{id}/retry-cleanup retries failed deletion. Orphan files and parser directories older than the configured one-hour TTL are swept. Downloads, OS/Docker backups, SQL dumps, provider retention, and filesystem snapshots are outside app deletion. Provider calls already sent cannot be recalled; OpenAI requests specify store:false, which is not a universal zero-retention guarantee.

## Review results and residual limits

Backend tests exercise direct IDs, cross-owner/cross-collection access, deletion races, malformed/resource-limited PDFs, invented quotes, leases, provider refusal/repair, endpoint rejection, and scoped vectors. Browser checks exercise hostile text rendering, actual PDF canvas output, review/export/version workflows, keyboard tabs, and automated WCAG checks.

pip-audit checks pinned runtime/development Python dependencies; npm audit checks frontend packages. Bandit has no medium/high findings after a narrow documented suppression for a private in-container tmpfs path. Low-level subprocess warnings are reviewed: commands use argument arrays, not a shell, and parser input keys are server-generated. Audit output is a dated advisory snapshot, not proof of absence of vulnerabilities.

Live model injection/quality remains unmeasured without a provider. Whole-machine disk quotas, guaranteed secure erasure, encrypted backups, provider-side retention enforcement, and public hosting are not implemented. The private local scope uses known development database credentials. Hosting requires authentication, explicit users/workspaces, runtime-role separation, deployment-specific network/SSRF policy, encrypted secret handling, rate limits, and a new review.
