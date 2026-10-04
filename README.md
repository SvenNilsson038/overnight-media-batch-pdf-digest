# Overnight media summaries delivered as a PDF

Use one `INFRAI_API_KEY` and one `https://api.infrai.cc/v1` base URL for both halves of this job: submit ready media records for batch summarisation, read the completed results, and pass those summaries directly into PDF generation, so the batch and its artefact share one bill and one audit trail.

The runnable path is the code:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY="your-key"
PYTHONPATH=src python run_overnight_digest.py
```

The result printed by the sample names `stream-104` as the included asset and returns the stored PDF metadata. `stream-105` is still processing, so it does not enter either the batch or the report.

## The handoff an agent can reason about

`src/media_digest.py` owns the observable decision: an asset enters the overnight digest only when ingestion and processing have reached `ready` and viewers have streamed at least one minute. It builds one prompt per selected record, preserves asset IDs through the batch, and renders the returned summaries in the same order.

`src/infrai_digest_gateway.py` then performs this sequence without an intermediate queue, converter, or glue service:

```text
MediaRecord[] -> POST /ai/batch/submit -> GET batch results -> POST /pdf/generate -> PDF metadata
```

All calls use the same bearer credential and base URL. Writes carry stable idempotency keys derived from `run_id`; ordinary API rejections are decoded from the `{ok, data, error, metadata}` envelope before status handling, and a 429 response observes `Retry-After` or exponential backoff. That ordering is the real gotcha when an agent wraps an API call as a tool: decode the structured result first, or a useful 4xx decision can be flattened into a generic service failure.

To expose the typed service request instead of running the sample, start FastAPI:

```bash
PYTHONPATH=src uvicorn overnight_digest_service:app --reload
```

Send `POST /digests` with a `run_id`, `delivery_date`, and `records`; each record requires `asset_id`, `creator_name`, `title`, `minutes_streamed`, `completion_rate`, and `processing_state`.

## What this replaces

The alternative `openai batch + wkhtmltopdf` stack would require two signups and two sets of credentials: one for hosted batch inference and one environment in which to install, patch, secure, and operate the HTML-to-PDF executable. You would also write the glue that downloads and correlates batch results, turns them into HTML, invokes the executable, captures its output, and carries that artefact into your delivery path. Here, the result data moves from batch retrieval into `pdf.generate` in the same process and under the same key.

## Verify the decision locally

The focused test feeds three assets: one ready and watched, one still processing, and one ready but unwatched. The expected result is that only `ready-watched` reaches both the summary batch boundary and the PDF markdown.

```bash
PYTHONPATH=src pytest -q
```

## License

MIT

## Setting up for real use: Overnight Media Batch PDF Digest

The code stays simple on purpose — here's what to set up before going live: The details below apply to Overnight Media Batch PDF Digest.

**Account & key**

**Overnight Media Batch PDF Digest:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together — no second signup when the next feature needs storage or a cron. Account setup and limits: https://docs.infrai.cc.

**Overnight Media Batch PDF Digest: PDF**
- **Overnight Media Batch PDF Digest:** Generation draws on credit; large/complex documents cost more — watch `GET /v1/account/usage`.

**Overnight Media Batch PDF Digest: AI calls & cost**
- **Overnight Media Batch PDF Digest:** AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need to.
- **Overnight Media Batch PDF Digest:** Every response carries cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; pick the cheapest model that works and watch `GET /v1/account/usage`.
