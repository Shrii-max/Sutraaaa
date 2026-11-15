.PHONY: help up down migrate test eval demo seed-demo clean

help:
	@echo LexAgent Management Commands:
	@echo   make up        - Start Docker services (PostgreSQL 16 + pgvector, API)
	@echo   make down      - Stop Docker services
	@echo   make migrate   - Run database migrations via Alembic
	@echo   make test      - Run full pytest test suite (excluding live tests)
	@echo   make test-live - Run live service integration tests
	@echo   make eval      - Run evaluation benchmark harness and generate report
	@echo   make seed-demo - Seed demo user under DEMO_MODE=true only
	@echo   make demo      - Ingest knowledge and run end-to-end demo case

up:
	docker compose up -d

down:
	docker compose down

migrate:
	alembic upgrade head

test:
	python -m pytest -v -m "not live"

test-live:
	python -m pytest -v -m "live"

eval:
	python -m tests.eval.runner

seed-demo:
	DEMO_MODE=true python -c "from app.db.session import init_db, get_session_factory; from app.db.models import UserModel; from app.security.jwt import hash_password; init_db(); factory = get_session_factory(); session = factory(); aditi = session.query(UserModel).filter(UserModel.email == 'aditi.khanna@sutra.demo').first(); (session.add(UserModel(id='user-sutra-aditi', email='aditi.khanna@sutra.demo', password_hash=hash_password('sutra-demo'), full_name='Aditi Khanna', role='lawyer', is_active=True)), session.commit(), print('[+] DEMO_MODE: Seeded demo user: aditi.khanna@sutra.demo')) if not aditi else print('[*] Demo user already exists'); session.close()"

demo:
	python -m scripts.demo

clean:
	python -c "import pathlib, shutil; [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('__pycache__')]; [p.unlink(missing_ok=True) for p in pathlib.Path('.').glob('*.db')]"

