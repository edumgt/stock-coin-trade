"""회원·모의투자 DB(MariaDB) 엔진과 세션 관리."""

from __future__ import annotations

from collections.abc import Generator, Iterator
from contextlib import contextmanager
from typing import Annotated

from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

_settings = get_settings()

engine = create_engine(
    _settings.database_url,
    pool_pre_ping=True,
    pool_size=_settings.db_pool_size,
    max_overflow=_settings.db_max_overflow,
    connect_args={"connect_timeout": _settings.db_connect_timeout},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@contextmanager
def session_scope() -> Iterator[Session]:
    """작업 단위 하나를 감싼다. 정상 종료 시 commit, 예외 시 rollback."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db() -> Generator[Session, None, None]:
    """요청 단위 세션 의존성. 라우트가 정상 반환하면 commit, 예외(ApiError 포함)면 rollback."""
    with session_scope() as db:
        yield db


DbSession = Annotated[Session, Depends(get_db)]
