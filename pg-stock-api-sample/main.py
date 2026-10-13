"""pg-stock OHLCV 크롤링·조회 API 샘플 진입점.

    uvicorn main:app --reload --port 8010

기동 시 APScheduler 가 OHLCV 증분 수집을 등록한다(SCHEDULER_ENABLED=false 로 끌 수 있다).
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from pgstock.api import ohlcv_db, openapi_ohlcv
from pgstock.config import get_settings
from pgstock.errors import install_exception_handlers

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def create_app() -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        scheduler = None
        if settings.scheduler_enabled:
            from pgstock.jobs.scheduler import start_scheduler

            scheduler = start_scheduler()
        yield
        if scheduler is not None:
            scheduler.shutdown(wait=False)

    app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan, debug=settings.debug,
                  docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url=None)
    install_exception_handlers(app)
    app.include_router(ohlcv_db.router)
    app.include_router(openapi_ohlcv.router)

    @app.get("/health")
    def health() -> dict:
        return {"ok": True, "service": "pg-stock-api-sample"}

    return app


app = create_app()
