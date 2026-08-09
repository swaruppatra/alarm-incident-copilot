# Incident and Ticket Enrichment Copilot

An AI copilot for alarm incident triage and ticket enrichment. It combines a candidate-built MCP server (alarm management + ticketing tools) with document RAG to turn a natural-language request into a cited, human-approved support ticket draft.

**Selected use case:** Incident and Ticket Enrichment Copilot — service teams facing a high-priority alarm need a ticket created/updated with accurate alarm context, similar historical cases, and documented troubleshooting guidance, without manually cross-referencing three separate systems.

## Main Capabilities

- Natural-language chat that plans and re-plans its next step turn by turn (not a fixed, hard-coded sequence) — see `docs/architecture.md`.
- Alarm and asset data via a candidate-built MCP server over the Alarm Management API (asset search, alarm retrieval, priority scoring, recommendations, correlation, flood analysis, KPI calculation, and more — see `docs/mcp-tool-catalog.md`).
- Ticket search/create/update via a second MCP server over a candidate-built mock ticketing API, with **explicit human confirmation required before any write**.
- Grounded answers with source citations from a Markdown document corpus (troubleshooting manuals, operating procedures, safety instructions, resolution notes, etc.) via RAG over Qdrant — see `docs/rag-design.md`.
- One combined workflow where MCP data and RAG citations appear together in the same answer, not as separate demos.
- A GUI (chat, ticket-draft approval, MCP execution trace, RAG citations, similar tickets, and a live audit/Ops tab).

## Technology Stack

| Layer | Choice |
|---|---|
| Language / runtime | Python 3.11, managed with `uv` |
| Orchestration | LangGraph `StateGraph` + LangChain |
| LLM | OpenAI or Anthropic, swappable via `LLM_PROVIDER` (see `docs/design-decisions.md`) |
| MCP | `mcp` Python SDK (FastMCP), `langchain-mcp-adapters` on the client side |
| Backend API | FastAPI |
| GUI | Gradio |
| Vector store | Qdrant |
| Embeddings | OpenAI `text-embedding-3-small` |
| Simulators (Alarm Management + Ticketing) | FastAPI + SQLite |
| Audit trail | SQLite, read directly by the GUI's Ops tab |
| Packaging | Docker + Docker Compose |
| Tests / lint | pytest, pytest-asyncio, ruff |
| CI | GitHub Actions (`.github/workflows/ci.yml`) |

## MCP Servers

Two in-house MCP servers, each wrapping one source system (see `docs/design-decisions.md` for why they're split, and `docs/mcp-tool-catalog.md` for full per-tool schemas/examples):

- **`mcp-servers/alarm-management/`** — 14 tools over the Alarm Management API simulator: `search_assets`, `get_asset_metadata`, `get_alarms`, `get_alarm_by_id`, `get_alarm_summary`, `get_alarm_trends`, `get_alarm_correlation`, `get_flood_analysis`, `get_rationalization_candidates`, `get_priority_score`, `get_kpi_definitions`, `get_operator_recommendations`, `generate_kpi_calculation`, `execute_kpi_calculation`.
- **`mcp-servers/ticketing/`** — 5 tools over the ticketing API simulator: `search_similar_tickets`, `list_open_tickets_for_assets`, `get_ticket`, `create_ticket` (write, confirmation-gated), `update_ticket` (write, confirmation-gated).

Both are independently runnable/testable — see "How to Start the MCP Server(s) Independently" in `docs/mcp-tool-catalog.md`.

## RAG Corpus and Ingestion

16 Markdown documents across 8 categories (troubleshooting manuals, operating procedures, alarm philosophy, maintenance guides, safety instructions, knowledge articles, resolution notes, engineering standards) under `rag/documents/`, grounded in the same assets/alarms the simulator returns. Ingestion: heading-aware chunking → OpenAI embeddings → Qdrant upsert, deterministic point IDs. Full design in `docs/rag-design.md`.

```bash
uv run python -m rag.ingestion.run
```

## Folder Structure

```text
apps/
  backend/        FastAPI app + LangGraph orchestration (the copilot itself)
  frontend/        Gradio GUI (Copilot tab + Ops/audit tab)
mcp-servers/
  alarm-management/  Candidate MCP server #1 -- wraps the Alarm Management API
  ticketing/          Candidate MCP server #2 -- wraps the ticketing API
simulator/          Alarm Management API simulator (FastAPI + SQLite)
ticketing/           Ticketing API simulator (FastAPI + SQLite)
rag/
  documents/       The source document corpus (Markdown + YAML frontmatter)
  ingestion/       Chunking, embedding, Qdrant upsert pipeline
  retrieval/       Query-time retrieval, filtering, citations, prompt-injection guarding
  tests/           golden_set.yaml + retrieval/generation eval scripts
tests/
  unit/            Pure-function tests -- no network, no external services
  integration/     MCP server + MCP client tests, mocking one side of each boundary
  e2e/             CHAIN-09 orchestration test against the real simulator + MCP server
test-data/         Seed fixtures (assets/alarms/tickets/KPI defs) both simulators load on startup
docs/               Everything listed in "Deliverables" -- architecture, MCP catalog, RAG design, etc.
scripts/           One-off tooling (test-data generation)
connectors/         Placeholder -- see "Assumptions" below
postman/*           Reference API spec the simulator was built and validated against (outside this repo's build context; see the assignment package)
```

## Quick Start

Prerequisites: Docker, and a `.env` file at the repo root (copy `.env.example` and fill in `LLM_API_KEY`).

```bash
docker compose up --build
```

Wait for the `copilot-frontend` service's log line:
```
* Running on local URL:  http://0.0.0.0:3000
```
Then open **http://localhost:3000** in a browser. That's the whole app -- a Copilot tab (chat, ticket-draft approval, citations, MCP trace) and an Ops tab (live audit trail).

If port 6333 is already in use by a Qdrant instance you're running outside this project, use `docker compose up --build --scale vector-store=0` instead, and add a `docker-compose.override.yml` pointing `copilot-backend`'s `VECTOR_STORE_URL` at your existing instance (e.g. `http://host.docker.internal:6333` on Docker Desktop).

To stop everything: `docker compose down`.

### Running without Docker

```bash
uv run uvicorn simulator.app.main:app --port 8000
uv run uvicorn ticketing.app.main:app --port 8100
MCP_TRANSPORT=streamable-http MCP_PORT=9000 uv run python -m mcp-servers.alarm-management.mcp
MCP_TRANSPORT=streamable-http MCP_PORT=9100 uv run python -m mcp-servers.ticketing.mcp
PYTHONPATH=. uv run uvicorn apps.backend.main:app --port 8080
PYTHONPATH=. uv run python -m apps.frontend.app   # http://localhost:3000
```

## Configuration

All configuration is environment-variable driven — see `.env.example` for the full list with comments. Key ones:

| Variable | Purpose |
|---|---|
| `ALARM_API_TOKEN` / `TICKETING_API_TOKEN` | Shared bearer secret between each simulator and its MCP server |
| `LLM_PROVIDER` / `LLM_API_KEY` / `LLM_MODEL` | Which LLM the copilot uses (`openai` or `anthropic`) |
| `VECTOR_STORE_URL` / `QDRANT_COLLECTION_NAME` | Where the RAG index lives |
| `EMBEDDING_MODEL` | Embedding model for ingestion + query time |
| `MCP_SERVER_URL` / `TICKETING_MCP_SERVER_URL` | Where the copilot backend reaches each MCP server |

No secrets are committed; `.gitignore` excludes `.env`.

## Tests

```bash
uv run pytest tests/unit           # pure-function unit tests
uv run pytest tests/integration    # MCP server + MCP client tests (mocked boundaries)
uv run pytest tests/e2e            # CHAIN-09 orchestration, real simulator + real MCP server, in-process
uv run pytest rag/tests            # placeholder + eval script location (see below)
uv run ruff check .                # lint
```

All of the above run in CI on every push/PR (`.github/workflows/ci.yml`) and need no external services or API keys.

Two additional scripts need a live stack (Qdrant + MCP servers running, plus a real `LLM_API_KEY`) and are run manually, not in CI:

```bash
python -m rag.tests.eval_retrieval    # retrieval quality against golden_set.yaml
python -m rag.tests.eval_generation   # generation quality (incl. the adversarial-document regression check) against the real agent
```

## Sample Interactions

The assignment's own example questions, all supported end to end:

- "Prepare an incident for the highest-priority active alarm in EastRefinery."
- "Find similar historical tickets for this compressor alarm."
- "Summarize the issue, likely cause, affected asset, and recommended action."
- "Add the applicable troubleshooting procedure to the ticket draft."
- "Show open tickets linked to correlated assets."

A larger set of GUI walk-through scenarios (including a failure/degraded-mode scenario) is in `tests/e2e/manual_gui_test_scenarios.md`.

## Architecture Summary

GUI → copilot backend (FastAPI + LangGraph) → either an MCP tool call (alarm-management or ticketing server → its source API) or a RAG retrieval call (Qdrant) → back into the same LangGraph turn → one grounded answer with both MCP data and document citations. Full request-flow walkthrough, component table, and diagram notes in `docs/architecture.md`.

## Assumptions

- One primary use case implemented completely (Incident and Ticket Enrichment Copilot), per the assignment's own instruction to prefer a smaller, fully integrated solution over a broad, incomplete one.
- Ticketing is a candidate-built mock API (one of the assignment's explicitly supported options), not a live Jira/ServiceNow/Azure DevOps/GitHub Issues account.
- The document corpus is synthetic, authored for this project and grounded in the simulator's own fixture data (assets/alarms) — not real company documents.
- Single-user, single-host local deployment target (Docker Compose); no multi-tenant auth.
- `connectors/` (from the suggested repo structure) is kept as an empty placeholder — this project keeps each source-system HTTP client (`AlarmManagementClient`, `TicketingClient`) alongside its own MCP server instead, so server and connector version together (see `docs/architecture.md`).

## Known Limitations

Full list, plus future work, in `docs/known-limitations.md`. Headline items: no hybrid search or re-ranking in retrieval, generation eval checks keyword/tool presence rather than faithfulness/relevance/accuracy, in-memory (not persistent) conversation checkpointing, and RAG ingestion has no delete/prune step for removed documents.
