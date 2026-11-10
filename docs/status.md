# Implementation status

Updated 10 November 2026.

## Delivered

Local v1 is implemented: PDF/text parsing with preserved originals; source versions and restoration; durable cancellable jobs; pgvector hybrid retrieval with versioned embedding profiles; OpenAI, OpenAI-compatible and Ollama generation adapters with separate embedding settings and a `local_lexical` retrieval profile; claim suggestions, confirmation and revisions; evidence validation and review; stored exports with provenance; deletion and orphan cleanup; a responsive source reader; Docker setup; generated API contracts; a fixture evaluation harness; and CI.

Hosted accounts, multi-tenancy, OCR, crawling and other v2 scope are not included.

## Verified

- 83 backend tests pass against a disposable PostgreSQL/pgvector database, plus offline evaluation-scoring tests.
- The frontend typecheck and production build pass; generated API types match the backend schema.
- Browser workflows (text and PDF samples, review, export, mobile layout, keyboard tabs, accessibility scan) pass in CI and against a fresh Docker install.
- The six-case fixture evaluation passes with exact citations and full labelled evidence recall. These are predefined synthetic scenarios, not a model-quality result.
- A fresh clone following the README Docker quick start completed the PDF sample workflow (investigate, accept, export) on 10 November 2026. See [verification](verification.md).

## Not yet accepted

Live AI quality. Live generation was tested only with `gemini-3.5-flash-lite` on synthetic samples with lexical retrieval. Earlier analysis versions returned correct outcomes and exact quotations but usually missed one expected context quotation. The current `grounded-evidence-v5` analysis was rejected by Gemini with HTTP 400 in its single live check, so live Gemini investigations do not currently work. No held-out live evaluation, semantic-embedding result or second provider has been tested. Details: [live validation](live-validation.md).
