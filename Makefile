.PHONY: install lint format test test-scenarios migrate dev-api dev-admin docker-up docker-down pre-commit

pre-commit:
	pre-commit install

install:
	pip install -r requirements-dev.txt

lint:
	python -m ruff check packages apps tests
	python -m ruff format --check packages apps tests
	python -m mypy packages/order_engine

format:
	python -m ruff format packages apps tests

test:
	set PYTHONPATH=packages;. && python -m pytest tests/ -v

test-scenarios:
	set PYTHONPATH=packages;. && python -m pytest tests/scenarios/ -v

test-dialogue:
	set PYTHONPATH=packages;. && python scripts/run_scenario_tests.py --mode direct

docker-up:
	docker compose -f infra/docker-compose.yml up -d

docker-down:
	docker compose -f infra/docker-compose.yml down

migrate:
	set PYTHONPATH=packages;. && python -m alembic upgrade head

dev-api:
	set PYTHONPATH=packages && python -m uvicorn apps.order_api.main:app --reload --host 0.0.0.0 --port 8000

dev-admin:
	cd apps/admin && npm run dev
