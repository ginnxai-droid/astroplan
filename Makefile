.PHONY: install run test lint fmt types guardrails validate validate-all gate-g1 gate-g2 migrate openapi openapi-check

install:
	pip install -e ".[dev]"

run:
	uvicorn app.main:create_app --factory --reload --port 8000

test:
	python -m pytest

lint:
	python -m ruff check app scripts tests alembic && python -m ruff format --check app scripts tests alembic

fmt:
	python -m ruff check --fix app scripts tests alembic && python -m ruff format app scripts tests alembic

types:
	python -m mypy app

guardrails:
	python scripts/check_guardrails.py

validate:
	python scripts/validate_step.py $(STEP)

validate-all:
	python scripts/validate_step.py --all

gate-g1:
	python scripts/validate_step.py --gate G1

gate-g2:
	python scripts/validate_step.py --gate G2

migrate:
	alembic upgrade head

openapi:
	python scripts/generate_openapi.py

# Gap 24: fail when the live schema no longer matches the committed snapshot.
openapi-check: openapi
	git diff --exit-code openapi.json
