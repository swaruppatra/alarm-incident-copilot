# This service imports apps.frontend.* as a namespaced package (apps/__init__.py
# lives one level up), so the build context must be the repo root, not this
# directory, e.g.:
#   docker build -f apps/frontend/Dockerfile .
# docker-compose.yml's copilot-frontend service already sets context: .
# accordingly, matching alarm-mcp/ticketing-mcp's own Dockerfiles.

FROM python:3.11-slim AS copilot-frontend

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY apps/frontend ./apps/frontend
COPY apps/__init__.py ./apps/__init__.py

ENV PYTHONPATH=/app
# Without this, Python fully buffers stdout when it's not a TTY (i.e. always,
# under `docker logs`) -- Gradio's own "Running on local URL" banner would
# never actually appear in the logs, just sit in the buffer indefinitely.
ENV PYTHONUNBUFFERED=1

EXPOSE 3000

CMD ["uv", "run", "python", "-m", "apps.frontend.app"]
