"""라우터 공통 의존성(로그인·CSRF)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any

from fastapi import Depends, Request

from app.core.errors import ApiError
from app.core.security import csrf_is_valid

UNAUTHORIZED_BODY: dict[str, Any] = {"error": "UNAUTHORIZED", "message": "로그인이 필요합니다."}
CSRF_INVALID_BODY: dict[str, Any] = {"error": "CSRF_INVALID", "message": "요청 검증에 실패했습니다. 화면을 새로고침해주세요."}


def current_member_id(request: Request) -> int | None:
    value = request.session.get("member_id")
    return int(value) if value else None


OptionalMemberId = Annotated[int | None, Depends(current_member_id)]


def login_required(**body: Any) -> Callable[[Request], int]:
    """로그인 회원 ID를 돌려주는 의존성을 만든다. 본문을 바꿔 모듈별 401 응답 형식을 유지한다."""
    payload = body or UNAUTHORIZED_BODY

    def dependency(request: Request) -> int:
        member_id = current_member_id(request)
        if not member_id:
            raise ApiError(401, **payload)
        return member_id

    return dependency


require_member_id = login_required()
MemberId = Annotated[int, Depends(require_member_id)]


def csrf_required(**body: Any) -> Callable[[Request], None]:
    payload = body or CSRF_INVALID_BODY

    def dependency(request: Request) -> None:
        if not csrf_is_valid(request):
            raise ApiError(403, **payload)

    return dependency


require_csrf = csrf_required()
