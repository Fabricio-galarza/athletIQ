from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings

settings = get_settings()

# Engine with schema isolation
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    connect_args={
        # 🔥 Dynamic schema per service
        "options": f"-csearch_path={settings.db_schema}"
    }
)

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_connection() -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception as e:
        print(f"DB connection error: {e}")
        return False