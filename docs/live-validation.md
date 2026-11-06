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


## Second diagnostic session

The user authorized a new bounded session after the original records were
preserved. No old budget or result was overwritten. Offline comparison found
11 text paragraphs versus4 PDF page passages; the per-source nonempty line
multisets matched exactly. Both formats supplied the preliminary estimate, so
there is no evidence of parser text loss behind the omitted context finding.

Provider-call records now retain only numeric HTTP status in `usage.http_status`
(0 means no response), alongside existing numeric usage. They do not retain raw
error bodies, request headers, credentials or transport error messages. Status
cannot be overwritten by a provider-supplied usage field.

Two targeted, single-HTTP investigations were attempted using the same exact
Gemini model: the existing PDF conflict collection, then the existing text
conflict collection. Both returned HTTP503, in3,762ms and1,181ms of provider time
(4,431ms and1,924ms end to end). The private guard stopped at two service failures
out of a12-attempt maximum. There were no automatic retries, quota/authentication
failures, accepted outputs or reported token usage in this session. Total known
external attempts across both sessions are8. The present failure is a provider
HTTP503 affecting both formats; the old session's unrecorded HTTP cause remains
unknown. No further model calls were made.

The general evidence instruction now asks for a context quotation when an earlier
estimate for the same entity, period and metric materially qualifies a final
measurement. It also requires omitting irrelevant estimates and preserving the
provisional/final distinction. This changes no fixture facts or validators;
`grounded-evidence-v2` records the policy change. Its live effect is unverified
because both requests failed before producing outputs. The missing-context gap
therefore remains open.

A future successful development run must demonstrate100% expected outcomes and
exact citations, plus3/3 expected conflict quotations, before final numeric gates
are frozen for the existing five-case held-out split. The earlier2/3 quotation
baseline is not an acceptance target. Gate freezing and held-out execution remain
pending this unresolved prerequisite; no held-out result has been manufactured.
A second provider/model and semantic embeddings remain outside authorization.

Private session2 records are `.local/live-api-session2.json`,
`.local/live-http-session2.jsonl` and `.local/live-call-budget-session2.json`.
The old records are preserved under `.local/session1-preserved/`. Current results
remain readable through the isolated API/UI, while the test-session guard blocks
additional inference. This guard is an ignored validation harness, not a product
provider setting. Starting a future session must explicitly retain the old record
and create a new measured budget; do not silently reset the guard.


The follow-up passed the full71-test backend suite on the disposable test database
and five offline evaluation-scoring/control tests. No hosted requests were used
by those checks. The evaluator now stops after its first failed live investigation
and writes the failed result, rather than continuing into more cases. `--format`
selects text or PDF development cases separately; its default preserves both.
The isolated instance's production frontend build also completed during restart.

[Draft numeric gates](live-quality-gates.json) retain the observed baseline and
explicitly record that freezing is blocked. After service availability returns
and a new bounded session is deliberately authorized/prepared, the existing
workflow can be staged as follows (these commands were not executed in session2):

```bash
.venv/bin/python scripts/evaluate.py --suite live --split development --format txt --output .local/development-next-text.json
# Only after text passes, perform PDF development with --format pdf.
# Only after all development prerequisites pass, freeze the numeric gates, then:
.venv/bin/python scripts/evaluate.py --suite live --split held_out --output .local/held-out-once.json
```

Keep a separately measured worker request budget and single-request diagnostic
control: script fail-fast prevents subsequent investigations, while provider
request/repair limits apply inside an investigation. The current session2 guard
remains stopped; these reproduction commands do not authorize resetting it.
