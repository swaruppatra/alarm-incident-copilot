.PHONY: install run up down test lint ingest eval-retrieval eval-generation

install:
	uv sync

run:
	docker compose up --build

up:
	docker compose up --build -d

down:
	docker compose down

test:
	uv run pytest tests/unit tests/integration tests/e2e rag/tests

lint:
	uv run ruff check .

ingest:
	uv run python -m rag.ingestion.run

eval-retrieval:
	uv run python -m rag.tests.eval_retrieval

eval-generation:
	uv run python -m rag.tests.eval_generation
