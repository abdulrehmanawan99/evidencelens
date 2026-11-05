# Implementation status

Updated 5 November 2026, Asia/Karachi.

## Delivered

Local v1 modules are implemented: PDF/text parsing and originals; source versions/recovery; durable jobs; pgvector hybrid retrieval and embedding profiles; three live-generation adapter contracts and separate embeddings; claim suggestions/confirmation/revisions; evidence validation/review; stored exports/provenance; deletion/orphan cleanup; responsive source reader; Docker setup; generated contracts; fixtures/evaluation harness; CI and release documentation.

The implementation is in /Users/apple/Desktop/evidencelens, an independent Git repository. At the initial handoff only EvidenceLens had been developed. Subsequent portfolio work is recorded below; hosted accounts and v2 features have not been started.

Updated delivery policy: these are GitHub portfolio projects, with up to three applications developed concurrently and no unnecessary infrastructure or speculative scope. The first active batch is EvidenceLens, Webhook Clinic, and CallMap. This changes the working policy, not the implementation status of the other applications. See AGENTS.md.

Continuation: Webhook Clinic and CallMap now have separate Desktop Git repositories and are being implemented in parallel. Private GitHub repositories and PRs are authorized under `abdulrehmanawan99`. Built-in subagents are permitted without Warp visibility. Suitable free API catalogs were checked; live inference remains blocked by missing provider credentials and unverified compatibility (see free-providers.md).

## Verified

The backend suite passed 60 tests, including parser limits, exact citations, ownership/collection isolation, version restoration, reindexing, provider contracts, refusal/repair behavior, leases, export snapshots, and deletion of excluded-source metadata. The frontend production build, API type generation, fixture evaluation, npm audit, and Python dependency audit have run. Actual browser screenshots are retained. Final verification details are in verification.md.

The fixture evaluation passed six text/PDF scenarios with six exact citations and all labeled relevant passages retrieved. Those scenarios are predefined, not a held-out live-model result. A separate five-case held-out corpus covers new entities, support/conflict, missing metrics, period mismatch, and document injection.

## Remaining acceptance

Live end-to-end generation/embedding checks and quality evaluation remain blocked because no live provider/key or local model is configured. MockTransport contract tests validate request/response handling, not actual remote compatibility or model quality. Two real provider configurations should be evaluated when available; numeric live quality gates must follow the first measured development baseline and be frozen before held-out execution.

This is an implemented local v1 candidate with explicit live acceptance still outstanding. It would be inaccurate to say only v2 remains or to mark full AI acceptance complete. GitHub publishing is a separate optional action.
