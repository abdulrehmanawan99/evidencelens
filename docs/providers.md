# Provider setup and evaluation

Fixture is the default and makes no model calls. It accepts only the bundled corpus and three known claims. Custom PDFs/text can still be ingested/read; arbitrary fixture investigations fail explicitly.

## Server configuration

Generation uses MODEL_MODE (fixture/openai/openai_compatible/ollama), GENERATION_MODEL, GENERATION_ENDPOINT, and GENERATION_API_KEY. Embeddings use EMBEDDING_PROVIDER (openai/openai_compatible/ollama/local_lexical), EMBEDDING_MODEL, EMBEDDING_ENDPOINT, EMBEDDING_API_KEY, and EMBEDDING_DIMENSIONS. OPENAI_API_KEY is a fallback for either key. Values are read when API/worker start. Keep the ignored .env private; the setup helper sets mode0600.

OpenAI generation uses /responses with store:false, strict text.format JSON schema, and max_output_tokens. Compatible chat uses /chat/completions with strict response_format and max_tokens. Ollama uses /api/chat with a JSON schema and /api/embed with truncate:false. Compatible providers must support these contracts; a model name alone does not prove capability.

Model IDs are supplied by the operator, not guessed. At least 12,000 configured context tokens are required; the default is16,000. Generation output is capped at2,000 tokens. The conservative UTF-8 byte estimator may underuse a model's true context; it is a bound, not precise token accounting. Embedding dimension/model mismatch fails validation.

Endpoints must use HTTPS, except an explicit set of trusted local hostnames/loopback for HTTP. Credentials, URL query strings, fragments, and redirects are rejected. Endpoint configuration is server-controlled, not user-supplied browser input. Container-local localhost is the container; use host.docker.internal to reach a host Ollama service on Docker Desktop.

## Operational flow

1. Configure models/endpoints/keys in ignored .env and restart the API/worker.
2. Choose Check provider. This computes a local vector (local_lexical) or makes a bounded embedding request (hosted/Ollama), plus a schema-generation request in live mode. Failures show sanitized codes.
3. Rebuild the search index for existing collections when the embedding profile changes.
4. Run the development evaluation and inspect actual citations/explanations.
5. Set numeric live interpretation/recall/abstention gates from that development baseline, record model/profile versions, then freeze gates before held-out evaluation.
6. Repeat with a second real configuration when available.

A bounded actual Gemini development run is recorded in [live validation](live-validation.md) and [evaluation-live.json](evaluation-live.json). Three text cases succeeded; the first PDF case failed after two unavailable-provider attempts. This is partial compatibility evidence, with an omitted context finding and no semantic-embedding acceptance. Quota (429) and authentication (401/403) errors stop after one request; existing bounded transient-service retries remain.

## Constrained Gemini generation with local lexical retrieval

The current authorization permits only the exact generation model
`gemini-3.5-flash-lite`. It supersedes the earlier Gemini3.8 and hosted embedding
candidates. Never call another model or a hosted embedding endpoint under this
profile. Keep billing disabled, use synthetic sources, and keep the supplied key
in private server configuration outside Git. This configuration is a compatibility
candidate; it does not establish live quality or model acceptance.

```dotenv
MODEL_MODE=openai_compatible
GENERATION_MODEL=gemini-3.5-flash-lite
GENERATION_ENDPOINT=https://generativelanguage.googleapis.com/v1beta/openai
# Set GENERATION_API_KEY privately; never commit its value.
EMBEDDING_PROVIDER=local_lexical
EMBEDDING_MODEL=hashed-lexical-demo-v1
EMBEDDING_DIMENSIONS=64
EMBEDDING_ENDPOINT=local
EMBEDDING_API_KEY=
CONTEXT_TOKENS=16000
```

`local_lexical` reuses the fixture's deterministic hashed word-count vectors and
normalization, entirely in process, with no HTTP or model calls. Its model label,
64 dimensions, and `local` endpoint are fixed regardless of embedding environment
values. It is lexical retrieval, not semantic embeddings or an embedding-model
acceptance result. Generation still sends selected passages and claims to Gemini.
The provider bar and persisted run provenance identify retrieval as
`local_lexical`. The profile has a distinct fingerprint from fixture and hosted
profiles; explicitly rebuild existing collection indexes after switching. Old
vectors cannot satisfy the new profile, even though fixture vectors use the same
algorithm. Switching back to fixture retains the original fixture profile.

Restart API/worker with this private configuration, choose **Check provider**, then
**Rebuild search index** on the isolated validation collection before evaluation.
The provider check runs local hashing plus Gemini generation; it makes no hosted
embedding request. Existing strict-schema response and exact-citation validation
still apply. Stop on authentication/quota failures; never substitute a model or
activate paid fallback. No live result is implied by this setup documentation.

## Reproduce

Against the running API:

```bash
.venv/bin/python scripts/evaluate.py --api http://127.0.0.1:8000 --suite fixture --output docs/evaluation-fixture.json
.venv/bin/python scripts/evaluate.py --api http://127.0.0.1:8000 --suite live --output docs/evaluation-live.json
# After development baseline review and freezing the live gates:
.venv/bin/python scripts/evaluate.py --api http://127.0.0.1:8000 --suite live --split held_out --output docs/evaluation-live-held-out.json
```

The corpus is fixtures/evaluation.json. Development cases run against both text and PDF samples. The held_out split separately evaluates five previously defined new-source cases. The script checks expected outcome, citation membership/exactness, labeled passage recall within the selected context, and expected evidence relations. These automated checks cannot fully judge whether an explanation is correct; human review remains required. It deletes only its own collections and records provider configuration and usage without keys.

Evidence recall now requires the expected labeled text to occur inside a valid
returned quotation with the expected relation. Merely retrieving the fact's
passage does not give the finding credit for quoting unrelated text elsewhere in
that passage. Retrieval recall is still reported separately. Regression checks
run with `python -m unittest discover -s scripts -p test_evaluate.py` without a
database or provider calls.

A fixture suite uses strict known-case regression assertions. Those assertions are not a calibrated threshold for general live quality. Evaluate live reasoning and document injection separately from deterministic citation enforcement.
