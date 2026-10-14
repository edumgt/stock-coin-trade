# ST ReAct market analysis

`POST /api/ai/analyze` keeps the existing text stream used by the common AI panel. Its backend now selects read-only tools, feeds their observations back to Qwen, and either queries again or answers. `POST /api/ai/react` returns the answer, execution traces, source metadata, iteration count and degraded status as JSON.

Both accept `question` (optional, up to 4,000 characters), `context` and `type`. Model input is bounded; very long questions and context are truncated. The existing configured Qwen model is retained. Qwen calls use native function calling with a context window capped at 4,096 tokens.

Allowed tools:

- `search_documents`: up to three ST Qdrant document excerpts. These are reference material, not current market observations.
- `stock_quote`: six-digit domestic stock code, KIS Testbed quote. Quote retrieval time is not an assertion that trading is open or that the last trade happened at that time.
- `stock_history`: up to 60 stored daily candles over the last 180 calendar days; latest close, MA5, MA20 and source date. Data older than four calendar days is marked stale; fewer than 20 candles is partial.
- `crypto_candles`: Binance/Korbit public daily candles, at most 30. The newest daily candle can still be open.

No order, amendment, cancellation, balance mutation, arbitrary SQL or URL execution tool is registered. Tool arguments are validated before provider calls. Tool/provider/document output is data and must not override the system policy. Execution traces expose tool name, status, source date and duration; internal reasoning text is not returned.

Limits: three tool-selection rounds followed by one final-answer round, at most four tool calls, 180-second overall deadline, at most 90 seconds per model request and 12 seconds waiting for each tool. Identical calls reuse their observation. One analysis at a time per application process; additional requests receive HTTP 429. Read-tool workers are bounded to two; provider calls that have already started may finish after their waiting timeout. Model errors return an explicitly partial result rather than an invented analysis. The existing frontend may include its previously retrieved RAG excerpts in the supplied context; the agent can add further tool observations.

Validation covers observation feedback, rejected order tools, repeat-call deduplication, deadlines, stale histories, bounded Qwen transport, stream compatibility and concurrent-request rejection. Deployment should include `react_agent.py`, `qwen_remote.py`, `api/routes/ai.py`, `api/schemas.py`, plus the common frontend progress label. No environment/key changes are required.
