# Provider setup and evaluation

Fixture is the default and makes no model calls. It accepts only the bundled corpus and three known claims. Custom PDFs/text can still be ingested/read; arbitrary fixture investigations fail explicitly.

## Server configuration

Generation uses MODEL_MODE (fixture/openai/openai_compatible/ollama), GENERATION_MODEL, GENERATION_ENDPOINT, and GENERATION_API_KEY. Embeddings use EMBEDDING_PROVIDER, EMBEDDING_MODEL, EMBEDDING_ENDPOINT, EMBEDDING_API_KEY, and EMBEDDING_DIMENSIONS. OPENAI_API_KEY is a fallback for either key. Values are read when API/worker start. Keep the ignored .env private; the setup helper sets mode0600.

OpenAI generation uses /responses with store:false, strict text.format JSON schema, and max_output_tokens. Compatible chat uses /chat/completions with strict response_format and max_tokens. Ollama uses /api/chat with a JSON schema and /api/embed with truncate:false. Compatible providers must support these contracts; a model name alone does not prove capability.

Model IDs are supplied by the operator, not guessed. At least 12,000 configured context tokens are required; the default is16,000. Generation output is capped at2,000 tokens. The conservative UTF-8 byte estimator may underuse a model's true context; it is a bound, not precise token accounting. Embedding dimension/model mismatch fails validation.

Endpoints must use HTTPS, except an explicit set of trusted local hostnames/loopback for HTTP. Credentials, URL query strings, fragments, and redirects are rejected. Endpoint configuration is server-controlled, not user-supplied browser input. Container-local localhost is the container; use host.docker.internal to reach a host Ollama service on Docker Desktop.

## Operational flow

1. Configure models/endpoints/keys in ignored .env and restart the API/worker.
2. Choose Check provider. This makes a bounded embedding request plus a schema-generation request in live mode. Failures show sanitized codes.
3. Rebuild the search index for existing collections when the embedding profile changes.
4. Run the development evaluation and inspect actual citations/explanations.
5. Set numeric live interpretation/recall/abstention gates from that development baseline, record model/profile versions, then freeze gates before held-out evaluation.
6. Repeat with a second real configuration when available.

The current report records live coverage as blocked; neither OpenAI, compatible remote service, nor Ollama was called. Fixture measurements and mocked contract tests are separate evidence. No numeric live quality thresholds or successful live results have been invented.

## Reproduce

Against the running API:

```bash
.venv/bin/python scripts/evaluate.py --api http://127.0.0.1:8000 --suite fixture --output docs/evaluation-fixture.json
.venv/bin/python scripts/evaluate.py --api http://127.0.0.1:8000 --suite live --output docs/evaluation-live.json
# After development baseline review and freezing the live gates:
.venv/bin/python scripts/evaluate.py --api http://127.0.0.1:8000 --suite live --split held_out --output docs/evaluation-live-held-out.json
```

The corpus is fixtures/evaluation.json. Development cases run against both text and PDF samples. The held_out split separately evaluates five previously defined new-source cases. The script checks expected outcome, citation membership/exactness, labeled passage recall within the selected context, and expected evidence relations. These automated checks cannot fully judge whether an explanation is correct; human review remains required. It deletes only its own collections and records provider configuration and usage without keys.

A fixture suite uses strict known-case regression assertions. Those assertions are not a calibrated threshold for general live quality. Evaluate live reasoning and document injection separately from deterministic citation enforcement.
