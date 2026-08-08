# This server imports simulator.app.models.*, so the build context must be
# the repo root (not this directory), e.g.:
#   docker build -f mcp-servers/alarm-management/Dockerfile .
# docker-compose.yml's alarm-mcp service already sets context: . accordingly.

FROM python:3.11-slim AS mcp-server

WORKDIR /app

# curl is used by docker-compose's healthcheck to probe the streamable-http
# endpoint; python:3.11-slim doesn't ship it by default.
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY simulator ./simulator
COPY mcp-servers/alarm-management ./mcp-servers/alarm-management

ENV PYTHONPATH=/app

# MCP_TRANSPORT defaults to stdio (see .env.example); docker-compose.yml
# overrides it to streamable-http so this container is reachable over the
# network from other services.
EXPOSE 9000

CMD ["uv", "run", "python", "-m", "mcp-servers.alarm-management.mcp"]
