import os
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker


def _build_url() -> str:
    host = os.environ.get("DB_HOST", "mariadb")
    port = os.environ.get("DB_PORT", "3306")
    name = os.environ.get("DB_NAME", "mockinv")
    user = os.environ.get("DB_USER", "mockinv")
    password = os.environ.get("DB_PASSWORD", "12345678!!")
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{name}?charset=utf8mb4"


engine = create_engine(_build_url(), pool_pre_ping=True, pool_size=5, max_overflow=5)
SessionLocal = scoped_session(sessionmaker(bind=engine, autoflush=False, autocommit=False))


@contextmanager
def session_scope():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        SessionLocal.remove()
