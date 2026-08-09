# This server imports both simulator.app.models.common (shared PaginationMeta)
# and ticketing.app.models, so the build context must be the repo root:
#   docker build -f mcp-servers/ticketing/Dockerfile .

FROM python:3.11-slim AS ticketing-mcp

WORKDIR /app

# curl is used by docker-compose's healthcheck to probe the streamable-http
# endpoint; python:3.11-slim doesn't ship it by default.
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY simulator ./simulator
COPY ticketing ./ticketing
COPY mcp-servers/ticketing ./mcp-servers/ticketing

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# MCP_TRANSPORT defaults to stdio (see .env.example); docker-compose.yml
# overrides it to streamable-http so this container is reachable over the
# network from other services.
EXPOSE 9100

CMD ["uv", "run", "python", "-m", "mcp-servers.ticketing.mcp"]
