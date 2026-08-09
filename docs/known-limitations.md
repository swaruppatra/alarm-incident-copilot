# Known Limitations

## RAG

- **No hybrid search.** Retrieval is vector-only (Qdrant cosine similarity); no BM25/keyword component alongside it. Purely semantic queries work well, but an exact-term query (an alarm ID, a part number) can underperform a keyword match.
- **No re-ranking.** Results are returned in raw similarity order straight from Qdrant; no cross-encoder or LLM re-ranking pass to improve precision on the top few results.
- **Retrieval score threshold is untuned.** `RETRIEVAL_SCORE_THRESHOLD` (0.35) is a starting point, not calibrated against the golden set's actual score distribution.
- **Upsert-only ingestion, no prune.** Re-running ingestion updates edited/added documents correctly (deterministic point IDs), but deleting a `.md` file from `rag/documents/` does not remove its already-ingested points from Qdrant — stale vectors can accumulate.
- **Single embedding provider, no fallback.** `EMBEDDING_MODEL` is OpenAI-only; no local/offline embedding fallback if the API is unavailable or the key is unset.
- **Prompt-injection defense is structural, not exhaustive.** `wrap_chunk_for_prompt()`'s delimiting protects against a document trying to impersonate a system instruction, but `flag_suspicious_patterns()`'s regex list is observability-only and will miss injection phrasings it wasn't written to match.

## Generation Evaluation

- **`eval_generation.py` checks keyword presence/absence and tool-call sets, not faithfulness/relevance/accuracy.** It confirms a required phrase is present, a forbidden phrase is absent, and the right tools were called — it does not check whether the answer is grounded in the retrieved context (faithfulness), whether it actually addresses the question (relevance), or whether it's factually correct against a reference answer (accuracy). Real scoring on those axes would need an LLM-as-judge pass or hand-written reference answers, which is out of this submission's scope.
- **Only one golden-set row (GS-11) currently has generation assertions filled in** (`answer_must_contain`/`answer_must_not_contain`/`expected_tools`); the rest are deliberately left as placeholders (see `golden_set.yaml`'s own header comment) since writing expected answers before the agent existed to produce them would have been guesswork.
- **Not part of CI.** `eval_generation.py` (like `eval_retrieval.py`) needs a real, billed LLM call and a live MCP/Qdrant stack, so it's a manual/local script, not a workflow that runs on every push.

## Orchestration

- **In-memory checkpointer (`MemorySaver`), not `SqliteSaver`.** Conversation state — mid-conversation history, and any write awaiting confirmation — does not survive a backend process restart. A production deployment would need a persistent checkpointer.
- **Single-turn tool-call budget, not a global one.** `MAX_TOOL_CALLS_PER_TURN` (8) caps one planning turn; there's no cap across an entire long-running conversation.
- **No cost/rate limiting on LLM calls.** Every planning step, RAG retrieval, and generation eval case is a real, billed API call with no budget guard.

## Ticketing

- **Mock ticketing API, not a real provider.** `ticketing/` is a candidate-built simulator, not a live Jira/Azure DevOps/ServiceNow/GitHub Issues integration — see `docs/design-decisions.md` for why.

## GUI / Operability

- **Gradio, functional but not a production UI.** No multi-user auth/session isolation — the thread ID lives in browser `localStorage`, so it's single-user-per-browser by design, not access-controlled.
- **Ops tab reads the audit SQLite file directly**, not through an API — requires `copilot-backend` and `copilot-frontend` to share a filesystem volume (works in the single-host Docker Compose setup this repo ships; would not work split across hosts without a real API layer).
- **Docker Compose only.** No Kubernetes/production orchestration manifests.

---

# Future Work

Roughly in priority order, based on what's above:

1. **Swap `MemorySaver` → `SqliteSaver`** (the dependency, `langgraph-checkpoint-sqlite`, is already installed) so conversation state survives a restart.
2. **Add a prune/delete step to RAG ingestion** so removing a document from `rag/documents/` actually removes its vectors from Qdrant.
3. **Tune `RETRIEVAL_SCORE_THRESHOLD`** against the golden set's real score distribution instead of the current unvalidated default.
4. **Add hybrid (vector + keyword) search and a re-ranking pass** to the retrieval layer.
5. **Extend `eval_generation.py` with an LLM-as-judge faithfulness/relevance scoring pass**, and fill in generation assertions for more `golden_set.yaml` rows beyond GS-11.
6. **Real ticketing provider integration** (Jira/ServiceNow/etc.) as an alternative to the mock API, behind the same MCP tool contracts.
7. **Multi-user auth on the GUI**, replacing the current single-user-per-browser thread-ID model.
8. **Rate limiting / cost guardrails** on LLM calls.
