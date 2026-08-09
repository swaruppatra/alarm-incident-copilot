# alarm-incident-copilot
The project contains an AI copilot for alarm incident triage and ticket enrichment. It combines a custom MCP server (alarm management + ticketing tools) with document RAG to turn a natural-language request into a cited, human-approved support ticket draft.

## Getting Started

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
