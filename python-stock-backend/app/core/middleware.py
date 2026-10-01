"""요청 감사 미들웨어.

- 현재 요청 정보를 ContextVar(``app.core.context``)에 올려 서비스 계층이 호출자를 알 수 있게 한다.
- 외부 API 테스트 경로의 응답과 4xx/5xx 응답 본문을 가로채 사용이력·시스템 오류 로그를 남긴다.
- 처리되지 않은 예외는 스택과 함께 기록한 뒤 다시 던져 ServerErrorMiddleware가 500을 보내게 한다.

응답 본문은 JSON일 때만, 그리고 필요한 경로에서만 메모리에 모으므로 스트리밍(SSE) 응답에는 영향이 없다.
"""

from __future__ import annotations

import contextlib
import json
import time
from collections.abc import Callable
from typing import Any
from urllib.parse import parse_qsl

from starlette.concurrency import run_in_threadpool
from starlette.datastructures import Headers
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.context import RequestInfo, current_request

API_USAGE_PREFIXES = (
    "/api/broker-test/", "/api/kis-chart/", "/api/kis-explorer/", "/api/kis-real/",
    "/api/aws-broker-test/", "/api/alpaca-test/", "/api/aws-alpaca-test/", "/api/crypto-exchange-test/",
)
ERROR_LOG_EXCLUDED_PREFIX = "/api/error-analysis/"
_MAX_CAPTURE_BYTES = 1_000_000

ResponseRecorder = Callable[[RequestInfo, int, dict[str, Any] | None, int | None, BaseException | None, dict[str, str], bool], None]


def _endpoint_name(scope: Scope) -> str | None:
    endpoint = scope.get("endpoint")
    return getattr(endpoint, "__name__", None) if endpoint else None


class RequestAuditMiddleware:
    def __init__(self, app: ASGIApp, *, recorder: ResponseRecorder):
        self.app = app
        self.recorder = recorder

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path: str = scope["path"]
        query_string = scope.get("query_string", b"").decode("latin-1")
        session = scope.get("session") or {}
        client = scope.get("client")
        member_id = session.get("member_id")
        info = RequestInfo(
            method=scope["method"],
            path=path,
            full_path=f"{path}?{query_string}" if query_string else path,
            member_id=int(member_id) if member_id else None,
            remote_addr=client[0] if client else None,
        )
        track_usage = path.startswith(API_USAGE_PREFIXES)
        started = time.perf_counter()
        state: dict[str, Any] = {"status": None, "capture": False, "chunks": [], "size": 0}
        token = current_request.set(info)

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status = message["status"]
                content_type = Headers(raw=message.get("headers", [])).get("content-type", "")
                state["status"] = status
                state["capture"] = "application/json" in content_type and (
                    track_usage or (status >= 400 and not path.startswith(ERROR_LOG_EXCLUDED_PREFIX))
                )
            elif message["type"] == "http.response.body" and state["capture"]:
                body = message.get("body", b"")
                if state["size"] <= _MAX_CAPTURE_BYTES:
                    state["chunks"].append(body)
                    state["size"] += len(body)
                if not message.get("more_body", False):
                    state["capture"] = False
                    info.endpoint = _endpoint_name(scope)
                    await self._record(info, state, started, None, query_string, track_usage)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as exc:
            info.endpoint = _endpoint_name(scope)
            state["status"] = 500
            state["chunks"] = []
            await self._record(info, state, started, exc, query_string, track_usage)
            raise
        finally:
            current_request.reset(token)

    async def _record(
        self,
        info: RequestInfo,
        state: dict[str, Any],
        started: float,
        exc: BaseException | None,
        query_string: str,
        track_usage: bool,
    ) -> None:
        body: dict[str, Any] | None = None
        if state["chunks"] and state["size"] <= _MAX_CAPTURE_BYTES:
            try:
                parsed = json.loads(b"".join(state["chunks"]))
                body = parsed if isinstance(parsed, dict) else {}
            except ValueError:
                body = {}
        duration_ms = max(0, int((time.perf_counter() - started) * 1000))
        query = dict(parse_qsl(query_string, keep_blank_values=True))
        # 감사 기록 실패가 응답을 막으면 안 된다.
        with contextlib.suppress(Exception):
            await run_in_threadpool(self.recorder, info, state["status"], body, duration_ms, exc, query, track_usage)
