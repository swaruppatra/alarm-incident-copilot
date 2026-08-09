# This simulator imports simulator.app.models.common (shared PaginationMeta/
# ErrorResponse), so the build context must be the repo root, e.g.:
#   docker build -f ticketing/Dockerfile .

FROM python:3.11-slim AS ticketing-api

WORKDIR /app

# curl is used by docker-compose's healthcheck.
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY simulator ./simulator
COPY ticketing ./ticketing
COPY test-data ./test-data

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8100

CMD ["uv", "run", "uvicorn", "ticketing.app.main:app", "--host", "0.0.0.0", "--port", "8100"]
