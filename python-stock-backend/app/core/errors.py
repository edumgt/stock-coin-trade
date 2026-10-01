"""JSON 오류 응답.

프런트엔드는 ``data.error || data.message``를 표시하므로 기존 Flask 응답 본문 형식을 그대로 유지한다.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ApiError(Exception):
    """상태 코드와 JSON 본문을 그대로 지정하는 애플리케이션 오류."""

    def __init__(self, status_code: int, **body: Any):
        super().__init__(body.get("message") or body.get("error") or str(status_code))
        self.status_code = status_code
        self.body = body


def unauthorized(message: str = "로그인이 필요합니다.", **extra: Any) -> ApiError:
    return ApiError(401, error="UNAUTHORIZED", message=message, **extra)


def json_error(status_code: int, **body: Any) -> JSONResponse:
    return JSONResponse(body, status_code=status_code)


def _validation_message(exc: RequestValidationError) -> str:
    parts = []
    for item in exc.errors()[:3]:
        if item.get("type") == "json_invalid":
            return "JSON 본문 형식이 올바르지 않습니다."
        location = ".".join(str(piece) for piece in item.get("loc", ()) if piece not in ("body", "query", "path"))
        parts.append(f"{location} 값이 올바르지 않습니다." if location else "요청 값이 올바르지 않습니다.")
    return " ".join(dict.fromkeys(parts)) or "요청 형식이 올바르지 않습니다."


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(exc.body, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Flask 시절과 같이 잘못된 요청은 400으로 응답한다(FastAPI 기본 422 대신).
        return JSONResponse({"error": "INVALID_REQUEST", "message": _validation_message(exc)}, status_code=400)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, dict) else {"error": "HTTP_ERROR", "message": str(exc.detail)}
        return JSONResponse(detail, status_code=exc.status_code, headers=getattr(exc, "headers", None))
