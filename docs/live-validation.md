# Bounded Gemini development validation

Executed 6 November 2026 through the actual API and durable worker, using only
`gemini-3.5-flash-lite` through the compatible chat adapter. Retrieval used the
explicit `local_lexical` profile: `hashed-lexical-demo-v1`, 64 dimensions, endpoint
`local`, fingerprint
`97a7a9861450e2b64371cdae0e4e44678a4cd3d885ee24d7a668c25670e50c92`.
No hosted embedding or alternate model was called. This provides partial live
generation compatibility evidence; it is not semantic embedding acceptance.

The isolated validation database on port55435 and
`.local/resume-validation-artifacts` were used. The original `.env`, artifacts
and backup were preserved. A private runtime harness restricted the model and
endpoint, capped the session at eight external attempts, and stopped further
calls after any quota/authentication error. Six attempts were made in total.

## Actual results

- Provider check succeeded with one generation request and local vector creation.
  Its job completed in2,492ms; provider time was1,804ms.
- All three synthetic text development investigations succeeded with one request
  each. Conflict, missing financial metric, and wrong-period outcomes matched the
  existing labels. All three returned quotations were exact supplied-source text.
  End-to-end durations were2,970/2,026/2,757ms; provider durations were
  2,457/1,360/2,307ms.
- The conflict case retrieved all three labeled passages but returned only the
  final1.20-million support and final1.05-million conflict quotations. It omitted
  the expected preliminary-estimate context quotation: quotation evidence recall
  was2/3, not a full quality pass. The wrong-period case correctly abstained and
  supplied one Q2 context quotation; the financial case supplied no findings.
- Explicit local-profile reindex completed for both text and PDF collections.
  PDF parsing/ingestion succeeded, but the first PDF investigation failed with
  `provider_unavailable` on both attempts allowed by the existing transient retry
  limit. Validation stopped immediately; the other two PDF cases were not run.
  The sanitized app record does not retain HTTP status or response body, so the
  underlying provider/network cause is unconfirmed. PDF generation is unvalidated.
- Six generation attempts were persisted: four successful and two unavailable.
  Successful calls reported3,555 prompt tokens and549 completion tokens. Failed
  calls returned no usage; their token consumption is unknown.

Both exact quotations in the successful text conflict case were inspected and
accepted through the review API, with explicit synthetic-development notes. A
saved reviewed Markdown export preserved both quotations and the Gemini/local
lexical provenance. This required no further model calls. Results and the failed
PDF run remain in the isolated instance; private detailed reports and the exported
brief are in `.local/live-api-validation.json` and `.local/live-reviewed-brief.md`.
The committed [summary](evaluation-live.json) contains sanitized measured results.

## Verification and limits

Quota429 now fails after one request, as authentication401/403 already did. Ten
focused backend regressions passed against disposable
`evidencelens_test_local` on55435, covering quota/authentication fail-fast behavior,
the retained two-attempt503 limit, existing generation contracts/citation repair,
and local-profile isolation/no-HTTP behavior. The restarted production frontend
build passed. No application database was used for destructive tests.

These are small synthetic development cases. No prompt tuning, repeated
successful inference, held-out evaluation, second-provider result or general
quality claim is included. A second model/provider is outside the current exact
model authorization. Remaining live PDF behavior and the missing context finding
are recorded gaps; do not replace this partial result with fixture scores.
