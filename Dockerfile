# This service imports rag.*, ticketing.app.models (which itself imports
# simulator.app.models.common), so the build context must be the repo root,
# matching mcp-servers/*/Dockerfile and apps/frontend/Dockerfile, e.g.:
#   docker build -f Dockerfile .
# docker-compose.yml's copilot-backend service already sets context: .
# accordingly.

FROM python:3.11-slim AS copilot-backend

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY apps/backend ./apps/backend
COPY apps/__init__.py ./apps/__init__.py
COPY rag ./rag
COPY ticketing ./ticketing
COPY simulator ./simulator

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8080

CMD ["uv", "run", "uvicorn", "apps.backend.main:app", "--host", "0.0.0.0", "--port", "8080"]
