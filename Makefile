.PHONY: sync lint format format-check typecheck test quality clean

sync:
	uv sync --all-groups

lint:
	uv run ruff check .

format:
	uv run ruff format .

format-check:
	uv run ruff format --check .

typecheck:
	uv run mypy src tests

test:
	uv run pytest --cov=job_runner_platform --cov-report=term-missing

quality:
	scripts/quality-gate.sh

clean:
	rm -rf .coverage .mypy_cache .pytest_cache .ruff_cache htmlcov
