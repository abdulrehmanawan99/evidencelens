# EvidenceLens agent guidance

## Portfolio policy

- EvidenceLens is one of ten GitHub portfolio applications. Keep the solution
  focused, understandable, and easy to run; avoid speculative enterprise features.
- Work on three applications concurrently: the first batch is EvidenceLens,
  Webhook Clinic, and CallMap. The earlier one-project-at-a-time rule is superseded.
- The main assistant coordinates and reviews built-in subagents. The user dropped
  the requirement for visibility in Warp; no Warp login or paid service is needed.
- Prefer direct code and necessary dependencies. Add infrastructure or abstractions
  only when the actual v1 workflow needs them. Preserve the working implementation.
- Verify meaningful behavior, document actual results, and protect secrets/data.
  GitHub publication, deployment, and paid services require separate authorization.

## Resume and current scope

- Canonical repository: `/Users/apple/Desktop/evidencelens`.
- Read `CODEX_HANDOFF.md`, `README.md`, and relevant `docs/` before changing behavior.
  Portfolio scope reference: `/Users/apple/Downloads/Ten_AI_Applications_PRD.md`.
  This file and current user instructions override outdated delivery policies.
- Local v1 is implemented; real generation/embedding integration and quality
  acceptance remain pending. A suggested provider is not a confirmed choice.
- Keep the editorial reading-room interface and claim-by-claim evidence workflow.
  Preserve exact citations, human review, and honest insufficient-evidence results.
- Do not add hosted identity, multitenancy, OCR, crawling, or v2 scope unless asked.
- A blocked live-provider decision must not prevent progress on the other two
  active portfolio projects. Do not mark blocked acceptance complete.

## Runtime and verification

- Inspect current processes, configuration, and ports before starting services.
  Do not print `.env` or credentials, overwrite configuration, or kill unknown apps.
- Preserve `evidencelens_v1_pgdata`, `.local/v1-artifacts`, and `.local/backups`.
  Keep the original PostgreSQL installation and stale project copy untouched.
- Backend tests delete application rows: use only disposable databases named
  `evidencelens_test_*`, never an application or browser database.
- Use Python 3.12 and Node 22.13+; the launcher honors `NODE_EXECUTABLE`.
  Avoid concurrent builds/services sharing `.next-v1` or artifact directories.
- Run checks appropriate to actual changes. Historical verification is historical;
  fixture and mocked contract results do not establish live AI quality.
- Do not choose providers, install models, or send documents to paid APIs merely
  because a handoff lists them as the next milestone.
- The user authorized private GitHub repositories and PRs under
  `abdulrehmanawan99`; prepare reviewed feature branches, but do not merge/deploy.
  Prefer free API options; `docs/free-providers.md` records metadata-only discovery.
