.PHONY: setup dev test e2e lint licenses
.DEFAULT_GOAL := help

setup:
	cd backend && uv sync

test:
	cd backend && uv run pytest -q

lint:
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app tests
