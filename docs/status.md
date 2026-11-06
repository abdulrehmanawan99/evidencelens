# Implementation status

Updated 6 November 2026, Asia/Karachi.

## Delivered

Local v1 modules are implemented: PDF/text parsing and originals; source versions/recovery; durable jobs; pgvector hybrid retrieval and embedding profiles; three live-generation adapter contracts and separate embeddings; claim suggestions/confirmation/revisions; evidence validation/review; stored exports/provenance; deletion/orphan cleanup; responsive source reader; Docker setup; generated contracts; fixtures/evaluation harness; CI and release documentation.

The implementation is in /Users/apple/Desktop/evidencelens, an independent Git repository. At the initial handoff only EvidenceLens had been developed. Subsequent portfolio work is recorded below; hosted accounts and v2 features have not been started.

Updated delivery policy: these are GitHub portfolio projects, with up to three applications developed concurrently and no unnecessary infrastructure or speculative scope. The first active batch is EvidenceLens, Webhook Clinic, and CallMap. This changes the working policy, not the implementation status of the other applications. See AGENTS.md.

Continuation: Webhook Clinic and CallMap now have separate Desktop Git repositories and are being implemented in parallel. Private GitHub repositories and PRs are authorized under `abdulrehmanawan99`. Built-in subagents are permitted without Warp visibility. Suitable free API catalogs were checked. The later Gemini-only synthetic development results are recorded in [live validation](live-validation.md).

## Verified

The backend suite passed 60 tests, including parser limits, exact citations, ownership/collection isolation, version restoration, reindexing, provider contracts, refusal/repair behavior, leases, export snapshots, and deletion of excluded-source metadata. The frontend production build, API type generation, fixture evaluation, npm audit, and Python dependency audit have run. Actual browser screenshots are retained. Final verification details are in verification.md.

The fixture evaluation passed six text/PDF scenarios with six exact citations and all labeled relevant passages retrieved. Those scenarios are predefined, not a held-out live-model result. A separate five-case held-out corpus covers new entities, support/conflict, missing metrics, period mismatch, and document injection.

## Remaining acceptance

The exact authorized model `gemini-3.5-flash-lite` passed the real provider check and three text development investigations using explicit `local_lexical` retrieval. All three outcomes and three quotations were valid, but one expected context finding was omitted. The first PDF investigation failed with `provider_unavailable` after two attempts, and further calls stopped. A later bounded diagnostic session made one PDF and one text request; both returned retained HTTP503 and the session stopped after two service failures. The general provisional-context instruction is now versioned as `grounded-evidence-v2`, but its live effect and held-out evaluation remain unverified. See [live validation](live-validation.md).

Local lexical retrieval makes no embedding-model calls and does not establish semantic embedding quality. PDF live validation and broader model quality remain incomplete. A second model/provider is blocked by the current exact-model authorization; no alternate or hosted embedding model was called. No held-out result or full model acceptance is claimed.

This is an implemented local v1 candidate with explicit live acceptance still outstanding. It would be inaccurate to say only v2 remains or to mark full AI acceptance complete. PR1 was merged by the user; follow-up changes use a fresh branch and PR.
