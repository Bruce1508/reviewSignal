# ReviewSignal AI — developer entrypoints.
# Runtime topology is documented in docs/deployment.md §3.

WEB := apps/web

.PHONY: help install up down logs migrate revision api worker web check format lint citations typecheck test test-py test-web

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  %-12s %s\n", $$1, $$2}'

install: ## Install Python and web dependencies
	uv sync
	cd $(WEB) && npm install

up: ## Start PostgreSQL and Redis
	docker compose up -d postgres redis

down: ## Stop all services
	docker compose down

logs: ## Tail service logs
	docker compose logs -f

migrate: ## Apply migrations
	uv run alembic upgrade head

revision: ## Autogenerate a migration: make revision m="add x"
	uv run alembic revision --autogenerate -m "$(m)"

api: ## Run the API with reload
	uv run uvicorn reviewsignal_api.main:app --reload --port 8000

worker: ## Run the RQ worker
	uv run python -m reviewsignal_worker.main

web: ## Run the Next.js dev server
	cd $(WEB) && npm run dev

format: ## Format Python
	uv run ruff format .

lint: ## Lint Python and web
	uv run ruff check .
	uv run ruff format --check .
	uv run python -m tools.check_citations
	cd $(WEB) && npm run lint

citations: ## Report every `<doc>.md §N` citation and the heading it resolves to
	uv run python -m tools.check_citations --report

typecheck: ## Type-check Python and web
	uv run pyright
	cd $(WEB) && npm run typecheck

test-py: ## Run Python tests (requires `make up`)
	uv run pytest

test-web: ## Build the web app
	cd $(WEB) && npm run build

test: test-py test-web ## Run all tests

check: lint typecheck test ## Full gate: lint, types, tests
	@echo "All checks passed."
