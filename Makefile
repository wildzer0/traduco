.PHONY: setup dev test e2e lint licenses
.DEFAULT_GOAL := help
PNPM = corepack pnpm
FAKE = cd tools/fake-llm && uv run --project ../../backend python -m fake_llm

help:
	@echo "Targets: setup dev test e2e lint licenses (see AGENTS.md)"

setup:
	cd backend && uv sync
	cd frontend && $(PNPM) install --frozen-lockfile

dev:
	@trap 'kill 0' INT TERM EXIT; \
	(cd backend && uv run uvicorn app.main:app --reload --port 8000) & \
	(cd frontend && $(PNPM) dev) & \
	($(FAKE)) & \
	wait

test:
	cd backend && uv run pytest -q
	cd backend && uv run pytest -q ../tools/fake-llm/tests ../tools/tests
	cd frontend && $(PNPM) test

e2e:
	cd frontend && $(PNPM) build && $(PNPM) e2e

lint:
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app tests
	cd backend && uv run mypy ../tools/fake-llm/fake_llm
	cd backend && uv run ruff check ../tools && uv run ruff format --check ../tools
	cd frontend && $(PNPM) lint

licenses:
	cd backend && uv run python ../tools/check-licenses.py
