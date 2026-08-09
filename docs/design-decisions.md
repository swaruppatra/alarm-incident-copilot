# Design Decisions

## Orchestration: hand-rolled LangGraph `StateGraph`, not `create_agent`

- Chose LangGraph's `StateGraph` (`apps/backend/graph/`) over LangChain's higher-level `create_agent` helper.
- Reason: this workflow needs explicit control over routing (RAG tool vs. MCP tool vs. respond), a hard pause for write-operation confirmation (`interrupt()`), and a typed, inspectable state object (`AgentState`) that the GUI's audit/trace views read directly — all easier to reason about and test as explicit nodes/edges than inside a general-purpose agent loop.
- Trade-off: more code to write and maintain than `create_agent`, in exchange for that control.

## Planner: `parallel_tool_calls=False`

- The planning LLM is bound with `parallel_tool_calls=False`, forcing exactly one tool call per planning step.
- Reason: this is what makes multi-step chaining genuine re-planning (decide the next step after seeing the previous result) rather than a pre-committed batch of calls, and it's what makes every routing function's `tool_calls[0]` assumption safe.

## LLM provider: swappable via `LLM_PROVIDER`

- `apps/backend/config.py::get_llm()` is the single factory every graph node calls; it branches on `LLM_PROVIDER` (`openai`/`anthropic`) and imports the provider SDK only inside its own branch, so switching providers is a one-line `.env` change, not a code change, and selecting `openai` never requires `langchain-anthropic` to be installed (or vice versa).

## Vector store: Qdrant

- Chosen for a simple local Docker Compose footprint (single `qdrant/qdrant` image, no managed-service dependency) and a straightforward Python client with the filtering (`FieldCondition`/`MatchValue`) this project needed.

## Chunking: heading-aware, two-stage

- `MarkdownHeaderTextSplitter` (H1/H2) first, `RecursiveCharacterTextSplitter` only as a fallback for oversized sections — see `docs/rag-design.md`. Chosen over flat character-based chunking because the corpus's own document structure (Symptom / Likely Causes / Recommended Actions, etc.) is already the right retrieval granularity; splitting on headers keeps each chunk topically coherent instead of cutting mid-thought at a fixed character count.

## MCP server boundaries: two servers, split by source system

- `mcp-servers/alarm-management/` and `mcp-servers/ticketing/` are separate FastMCP servers rather than one combined server.
- Reason: each wraps exactly one source system's API, with its own auth token, its own base URL, its own client. Keeping that boundary at the server level (not just a module level) matches how they'd actually be deployed/scaled/rotated independently in production, and keeps each server "independently runnable and testable" per the assignment's requirement.

## Ticketing provider: candidate-built mock API

- Built a minimal ticketing API simulator (`ticketing/`) rather than integrating a real Jira/Azure DevOps/ServiceNow/GitHub Issues account.
- Reason: the assignment explicitly lists this as one of the supported options, and it keeps the time box focused on the MCP+RAG integration pattern (which is what's actually graded) rather than a third-party API's specific auth flow/rate limits/sandbox account setup.

## Checkpointer: `MemorySaver`, not `SqliteSaver`

- The compiled graph uses LangGraph's in-memory `MemorySaver`, not `SqliteSaver`, even though `interrupt()` requires *some* checkpointer to work at all.
- Trade-off, taken deliberately: conversation state (mid-conversation history, any paused-awaiting-confirmation write) does not survive a backend process restart. Acceptable for this assignment's scope; flagged in `docs/known-limitations.md` as the first thing to change for anything beyond a local demo.

## Audit trail: direct SQLite read, not an API

- The GUI's Ops tab (`apps/frontend/audit_reader.py`) reads `audit_trail.sqlite3` directly rather than calling a backend endpoint, via a Docker volume (`./var`) shared between `copilot-backend` and `copilot-frontend`.
- Reason: avoids building and maintaining a whole read API surface just for an internal observability tab, at the cost of frontend/backend no longer being fully decoupled processes (they must share a filesystem volume). Acceptable for a single-host Docker Compose deployment; would need to become a real API (or a shared observability backend) for a multi-host deployment.

## Prompt versioning: one constants module, not a prompt registry

- All three system prompts live in `apps/backend/prompt.py` behind a single `PROMPT_VERSION` string, logged on every audit row.
- Reason: lightweight and sufficient to answer "which prompt version produced this answer" after the fact, without the overhead of a full prompt-management service for a project this size.

## RAG safety: observability-only injection detection, not content blocking

- `flag_suspicious_patterns()` logs a warning when a retrieved chunk matches a known injection phrasing; it never removes, edits, or blocks the chunk itself.
- Reason: the actual defense is structural (`wrap_chunk_for_prompt()`'s delimiting + forged-delimiter neutralization, described in `docs/rag-design.md`), which works regardless of whether the pattern list happens to catch a given phrasing. The pattern flagging exists for visibility/logging, not as the primary safety mechanism — a regex allowlist/blocklist would be trivially bypassed and was never meant to be the real control.
