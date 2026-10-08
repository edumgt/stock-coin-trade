"""FastAPI 애플리케이션 팩토리.

실행: ``uvicorn app.main:app --host 0.0.0.0 --port 8200``

미들웨어 순서(바깥 → 안): CORS → 서버 세션(Redis) → 요청 감사 → 라우터.
요청 감사 미들웨어가 세션 안쪽에 있어 로그인 회원 ID를 감사 로그에 남길 수 있다.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.concurrency import run_in_threadpool
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.errors import install_exception_handlers
from app.core.middleware import RequestAuditMiddleware, ExternalReadLimitMiddleware
from app.core.sessions import MemorySessionStore, RedisSessionStore, ServerSessionMiddleware, SessionStore
from app.services.audit import record_response

log = logging.getLogger(__name__)


class PathScopedCORSMiddleware:
    """경로별로 다른 CORS 정책을 적용한다.

    - ``/api/*``   : 로컬 개발 origin만 허용하고 자격증명(쿠키)을 함께 보낸다.
    - ``/openapi/*``: 외부 연동용이므로 모든 origin을 허용하되 자격증명은 받지 않는다.
    """

    def __init__(self, app: ASGIApp, *, api_origin_regex: str):
        self.default = app
        self.api = CORSMiddleware(app, allow_origin_regex=api_origin_regex, allow_credentials=True,
                                  allow_methods=["*"], allow_headers=["*"])
        self.open_api = CORSMiddleware(app, allow_origins=["*"], allow_credentials=False,
                                       allow_methods=["GET", "POST", "OPTIONS"],
                                       allow_headers=["Authorization", "Content-Type"], max_age=86400)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            path: str = scope["path"]
            if path.startswith("/api/"):
                await self.api(scope, receive, send)
                return
            if path.startswith("/openapi/"):
                await self.open_api(scope, receive, send)
                return
        await self.default(scope, receive, send)


def _noop_recorder(*_: object) -> None:
    """감사 기록을 끈 환경(테스트)용."""


def build_session_store(settings: Settings) -> SessionStore:
    if settings.session_store.lower() == "memory":
        log.warning("SESSION_STORE=memory: 로그인 세션이 프로세스 메모리에만 저장됩니다(로컬 개발 전용).")
        return MemorySessionStore()
    return RedisSessionStore(settings.redis_url, settings.redis_session_key_prefix)


def create_app(settings: Settings | None = None, *, session_store: SessionStore | None = None) -> FastAPI:
    settings = settings or get_settings()
    store = session_store or build_session_store(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        scheduler = None
        if settings.app_startup_tasks:
            from app.startup import run_startup_tasks

            await run_in_threadpool(run_startup_tasks)
            if settings.scheduler_enabled:
                from app.jobs.scheduler import start_scheduler

                scheduler = start_scheduler()
        yield
        if scheduler is not None:
            scheduler.shutdown(wait=False)

    app = FastAPI(
        title=settings.app_name,
        version="2.0.0",
        lifespan=lifespan,
        debug=settings.debug,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
        middleware=[
            Middleware(PathScopedCORSMiddleware, api_origin_regex=settings.cors_api_origin_regex),
            Middleware(ExternalReadLimitMiddleware),
            Middleware(
                ServerSessionMiddleware,
                store=store,
                secret_key=settings.secret_key,
                cookie_name=settings.session_cookie_name,
                max_age=settings.session_lifetime_seconds,
                same_site=settings.session_cookie_samesite,
                https_only=settings.session_cookie_secure,
            ),
            Middleware(RequestAuditMiddleware, recorder=record_response if settings.audit_enabled else _noop_recorder),
        ],
    )
    app.state.settings = settings
    app.state.session_store = store
    install_exception_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()
