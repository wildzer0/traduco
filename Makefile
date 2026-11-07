.PHONY: setup dev test e2e lint licenses
.DEFAULT_GOAL := help

setup:
	cd backend && uv sync

test:
	cd backend && uv run pytest -q
	cd backend && uv run pytest -q ../tools/fake-llm/tests

lint:
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app tests && uv run mypy ../tools/fake-llm/fake_llm
	cd backend && uv run ruff check ../tools && uv run ruff format --check ../tools
