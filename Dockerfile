# Placeholder Dockerfile for the copilot backend.
# Replace with a real multi-stage build once apps/backend is implemented.

FROM python:3.11-slim AS backend

WORKDIR /app

COPY apps/backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY apps/backend ./apps/backend
COPY mcp-servers ./mcp-servers
COPY rag ./rag
COPY connectors ./connectors

EXPOSE 8080

CMD ["python", "-m", "apps.backend.main"]
