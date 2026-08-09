# This simulator loads its fixtures from test-data/ (see
# simulator/app/data/seed_loader.py's TEST_DATA_DIR), so the build context
# must be the repo root, e.g.:
#   docker build -f simulator/Dockerfile .
# docker-compose.yml's alarm-api service sets context: . accordingly.

FROM python:3.11-slim AS alarm-api

WORKDIR /app

# curl is used by docker-compose's healthcheck.
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY simulator ./simulator
COPY test-data ./test-data

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "simulator.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
