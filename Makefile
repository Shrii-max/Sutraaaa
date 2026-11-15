.PHONY: help up down migrate test eval demo clean

help:
	@echo LexAgent Management Commands:
	@echo   make up       - Start Docker services (PostgreSQL 16 + pgvector, API)
	@echo   make down     - Stop Docker services
	@echo   make migrate  - Run database migrations via Alembic
	@echo   make test     - Run full pytest test suite
	@echo   make eval     - Run evaluation benchmark harness and generate report
	@echo   make demo     - Ingest dummy knowledge and run end-to-end demo case

up:
	docker compose up -d

down:
	docker compose down

migrate:
	alembic upgrade head

test:
	python -m pytest -v

eval:
	python -m tests.eval.runner

demo:
	python -m scripts.demo

clean:
	python -c "import pathlib, shutil; [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('__pycache__')]; [p.unlink(missing_ok=True) for p in pathlib.Path('.').glob('*.db')]"

