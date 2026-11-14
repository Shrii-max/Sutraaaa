"""Initialize database tables and pgvector extension."""

from app.db.session import init_db, get_engine


def main():
    engine = get_engine()
    print(f"Initializing database at: {engine.url}")
    init_db(engine)
    print("Database initialization complete.")


if __name__ == "__main__":
    main()

