.PHONY: install run test lint ingest up down

install:
	pip install -r apps/backend/requirements.txt

run:
	docker compose up --build

up:
	docker compose up --build -d

down:
	docker compose down

test:
	pytest tests/unit tests/integration tests/e2e rag/tests

lint:
	ruff check .

ingest:
	python -m rag.ingestion.run --source rag/documents --target rag/index
