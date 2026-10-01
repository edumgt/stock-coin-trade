"""요청 감사 미들웨어가 응답마다 호출하는 기록기(API 사용이력 + 시스템 오류 로그)."""

from __future__ import annotations

import traceback
from http import HTTPStatus
from typing import Any

from app.core.context import RequestInfo
from app.core.middleware import ERROR_LOG_EXCLUDED_PREFIX
from app.services.api_usage import record_api_usage
from app.services.error_analysis import record_error


def record_response(
    info: RequestInfo,
    status: int,
    body: dict[str, Any] | None,
    duration_ms: int | None,
    exc: BaseException | None,
    query: dict[str, str],
    track_usage: bool,
) -> None:
    if track_usage and exc is None:
        record_api_usage(info, status, body, duration_ms, query)
    if status >= 400 and not info.path.startswith(ERROR_LOG_EXCLUDED_PREFIX):
        body = body or {}
        try:
            status_text = f"{status} {HTTPStatus(status).phrase.upper()}"
        except ValueError:
            status_text = str(status)
        message = body.get("message") or body.get("error") or (str(exc) if exc else None) or status_text
        record_error(
            source="SERVER", severity="CRITICAL" if status >= 500 else "WARNING",
            status=status, method=info.method, path=info.full_path,
            error_type=type(exc).__name__ if exc else "HTTPError",
            message=message,
            stack_trace="".join(traceback.format_exception(exc)) if exc else None,
            request_meta={"endpoint": info.endpoint, "remoteAddr": info.remote_addr}, member_id=info.member_id,
        )
