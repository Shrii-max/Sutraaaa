"""Database engine, session management, and trigger initialization for append-only audit logs."""

from typing import Generator
from sqlalchemy import create_engine, text, event
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.config import get_settings

Base = declarative_base()


def get_engine():
    """Create SQLAlchemy 2.0 engine from settings."""
    settings = get_settings()
    db_url = settings.DB_URL

    connect_args = {}
    if db_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    elif "postgresql" in db_url:
        connect_args["connect_timeout"] = 2

    engine = create_engine(
        db_url,
        echo=False,
        connect_args=connect_args,
        pool_pre_ping=True,
    )
    return engine


_engine = None
_SessionLocal = None


def reset_engine():
    global _engine, _SessionLocal
    _engine = None
    _SessionLocal = None


def get_session_factory():
    global _engine, _SessionLocal
    if _engine is None:
        _engine = get_engine()
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding database session."""
    factory = get_session_factory()
    db = factory()
    try:
        yield db
    finally:
        db.close()


def install_audit_append_only_triggers(engine):
    """Installs database-level triggers to enforce append-only immutability on audit_logs."""
    dialect_name = engine.dialect.name

    with engine.connect() as conn:
        if dialect_name == "postgresql":
            conn.execute(text("""
                CREATE OR REPLACE FUNCTION audit_logs_block_modifications()
                RETURNS TRIGGER AS $$
                BEGIN
                    RAISE EXCEPTION 'audit_logs table is append-only: UPDATE and DELETE operations are prohibited';
                END;
                $$ LANGUAGE plpgsql;
            """))
            conn.execute(text("DROP TRIGGER IF EXISTS audit_logs_immutable ON audit_logs;"))
            conn.execute(text("""
                CREATE TRIGGER audit_logs_immutable
                BEFORE UPDATE OR DELETE ON audit_logs
                FOR EACH ROW
                EXECUTE FUNCTION audit_logs_block_modifications();
            """))
            conn.commit()
        elif dialect_name == "sqlite":
            conn.execute(text("""
                CREATE TRIGGER IF NOT EXISTS audit_logs_no_update
                BEFORE UPDATE ON audit_logs
                BEGIN
                    SELECT RAISE(ABORT, 'audit_logs table is append-only: UPDATE blocked');
                END;
            """))
            conn.execute(text("""
                CREATE TRIGGER IF NOT EXISTS audit_logs_no_delete
                BEFORE DELETE ON audit_logs
                BEGIN
                    SELECT RAISE(ABORT, 'audit_logs table is append-only: DELETE blocked');
                END;
            """))
            conn.commit()


def init_db(engine=None):
    """Initialize database extension (pgvector), all tables, and audit immutability triggers."""
    if engine is None:
        engine = get_engine()

    # Enable pgvector if PostgreSQL
    if "postgresql" in str(engine.url):
        try:
            with engine.connect() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
                conn.commit()
        except Exception:
            pass

    Base.metadata.create_all(bind=engine)
    try:
        install_audit_append_only_triggers(engine)
    except Exception:
        pass
