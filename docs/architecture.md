# Architecture

## Overview

- **Use case:** Incident and Ticket Enrichment Copilot — turns a natural-language request about an alarm into a cited, human-approved support ticket draft.
- **Orchestration:** a LangGraph `StateGraph` agent (`apps/backend/graph/`) that plans one tool call at a time, executes it, and re-plans — not a fixed, hard-coded sequence.
- **Two integration paths that must combine in one workflow:** structured data via MCP (Alarm Management + Ticketing), and unstructured knowledge via RAG (Qdrant + a Markdown document corpus).
- **Human-in-the-loop:** ticket create/update calls always pause for explicit user confirmation before executing (`await_confirmation_node`, via LangGraph's `interrupt()`).

## Components

| Component | Where it lives |
|---|---|
| GUI | `apps/frontend/` (Gradio) |
| Copilot orchestration | `apps/backend/graph/` (LangGraph `StateGraph`), `apps/backend/main.py` (FastAPI) |
| MCP client / tool registry | `apps/backend/mcp_clients.py` (`MultiServerMCPClient`) |
| Candidate-developed MCP servers | `mcp-servers/alarm-management/`, `mcp-servers/ticketing/` |
| Alarm Management API (simulator) | `simulator/` |
| Ticketing API (candidate-built mock) | `ticketing/` |
| RAG ingestion pipeline | `rag/ingestion/` |
| Retrieval service | `rag/retrieval/` |
| Document store (source corpus) | `rag/documents/` |
| Vector index | Qdrant (`vector-store` service in Docker Compose) |
| Domain models | `simulator/app/models/`, `ticketing/app/models/`, `rag/retrieval/models.py`, `apps/backend/models.py` |
| Auth boundary | Bearer token, validated inside each simulator API (`simulator/app/auth.py`, `ticketing/app/auth.py`); MCP servers hold and forward the token, never expose it |
| Observability | SQLite audit trail (`apps/backend/audit.py`), read live by the GUI's Ops tab (`apps/frontend/audit_reader.py`) |

*Note on `connectors/`:* the required-structure template lists a top-level `connectors/` folder; this repo keeps each source-system HTTP client (`AlarmManagementClient`, `TicketingClient`) next to its own MCP server instead (`mcp-servers/*/client.py`), so the server and its connector deploy and version together. `connectors/` is kept as an empty placeholder for structural parity — nothing currently lives there. Flagging this as a deliberate deviation, not an oversight.

## Request Flow

### MCP path (structured data)

1. User message arrives at `POST /chat` (`apps/backend/main.py`).
2. `classify_intent_node` labels the intent (e.g. `prepare_incident`).
3. `plan_node` asks the LLM (tools bound, `parallel_tool_calls=False`) to pick the next single tool call, or decide it has enough information.
4. `call_mcp_tools_node` invokes that tool through the MCP toolset loaded by `mcp_clients.py`, records a trace entry (name, args, duration, status, retry_count, result), and loops back to step 3 — so multi-step chaining (e.g. alarm → priority score → recommendations) happens by re-planning after every result, not a pre-built pipeline.
5. A write tool (`create_ticket`/`update_ticket`) is never executed directly — it's captured as `pending_write` and routed to `await_confirmation_node`, which pauses the graph via `interrupt()` until the GUI sends back an approve/reject.
6. `synthesize_answer_node` composes the final grounded answer from whatever alarm/ticket/document context has been gathered.

### RAG path (unstructured knowledge)

1. If the planner calls the `search_documentation` tool, `retrieve_docs_node` runs instead of `call_mcp_tools_node`.
2. `rag/retrieval/retriever.py` embeds the query, searches Qdrant (with optional `asset_id`/`doc_type` filters), and checks the best score against `RETRIEVAL_SCORE_THRESHOLD` — below it, `confident=False` and the node returns an explicit "no relevant documentation found" message instead of a weak/hallucinated citation.
3. Every retrieved chunk is passed through `wrap_chunk_for_prompt()` before it ever reaches the LLM — delimited and any forged delimiter sequences inside the content neutralized, so text embedded in a document can't impersonate a system instruction.
4. Citations (source path, section, score, snippet) are attached to the graph state and returned to the GUI alongside the answer.

### Combined example

"Prepare an incident for the highest-priority active alarm in EastRefinery" touches both paths in one turn: `get_alarms` (site filter) → `get_priority_score` → `get_operator_recommendations` → `search_similar_tickets` (MCP/ticketing) → `search_documentation` (RAG, troubleshooting doc for that alarm type) → `synthesize_answer_node` merges both into one answer with a ticket draft, citations, and the full MCP trace — all visible in the GUI.

## Architecture Diagram

This repo currently has two diagrams, not one, and neither is the full picture on its own:

- `docs/agent-graph.png` — auto-generated from the compiled LangGraph via `graph.get_graph().draw_mermaid_png()` (see `apps/backend/graph/build.py`). This shows the **orchestration graph's nodes and edges only** (classify → plan → call_mcp_tools/retrieve_docs → synthesize → await_confirmation → execute_write → respond). It does not show the GUI, the MCP servers, the simulators, or the RAG ingestion/index side.
- `docs/architecture-diagram.png` — The **full system diagram** containing: GUI, copilot orchestration, MCP client, both MCP servers, Alarm Management API, RAG ingestion pipeline, retrieval index, document store, observability, and the auth boundary, with both the MCP and the RAG paths visible end to end.

