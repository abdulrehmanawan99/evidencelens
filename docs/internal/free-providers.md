# Free API discovery — 5 November 2026

The portfolio should prefer free APIs. No paid service was enabled and no live
inference request was made during this discovery. Provider keys are absent from
the inspected process environment and EvidenceLens remains in fixture mode.

## Public catalogs actually fetched

Both OpenRouter catalog endpoints returned successfully without authentication:

- `https://openrouter.ai/api/v1/models`
- `https://openrouter.ai/api/v1/embeddings/models`

The generation catalog listed `xingchen-agi/xing4.0-29b-a4b:free` and
`nvidia/nemotron-3.5-super-vl:free` with zero prompt/completion pricing and
`response_format` plus `structured_outputs` parameters. The embedding catalog
listed `nvidia/nemotron-3.5-embed-1b:free` with zero prompt/completion pricing.
These are candidate configurations, not tested or accepted providers. Catalog
metadata does not establish strict-schema compatibility, embedding dimensions,
availability, privacy suitability, or quality for this application.

## Activation boundary

OpenRouter requires an API key for inference, including its free variants.
Its free variants are rate limited and do not require buying credits. Keep a
specific `:free` model pinned; do not enable paid fallback or buy credits. Recheck
current pricing, capabilities, and account limits before making requests. No
OpenRouter key was found in the inspected environment, so activation remains
blocked; do not invent credentials or reuse the coding-agent login as an API key.

If configured later, use the existing compatible generation/embedding adapters
with endpoint `https://openrouter.ai/api/v1`. Verify actual embedding dimensions
and request compatibility, run the provider capability check, then rebuild the
collection index. Do not change the current index or `.env` based on catalog data
alone. Run development evaluation before freezing gates and using held-out data.
Use only synthetic samples for initial checks.

Groq also documents speech-to-text free-tier limits for `whisper-large-v3-turbo`,
which is a possible CallMap provider. It requires its own account/API key; no Groq
key is configured in the inspected environment. No speech request was made.

## Sources

- [OpenRouter free models and limits](https://openrouter.ai/collections/free-models)
- [OpenRouter model catalog contract](https://openrouter.ai/docs/api/api-reference/models/get-models)
- [OpenRouter embedding catalog contract](https://openrouter.ai/docs/api/api-reference/embeddings/list-embeddings-models)
- [Groq speech-to-text contract and file limits](https://console.groq.com/docs/speech-to-text)

Free pricing and model availability can change. Free-tier data handling can differ
from paid services; document privacy/provider terms before sending private sources.
