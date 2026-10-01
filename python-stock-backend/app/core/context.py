"""요청 컨텍스트.

Flask의 ``request``/``session`` 전역 대신 ContextVar로 현재 요청 정보를 전달한다.
감사 로그(API 사용이력·시스템 오류)가 라우트 밖(게이트웨이·백그라운드)에서도 호출자를 알 수 있게 한다.
스레드풀에서 실행되는 동기 라우트에도 컨텍스트가 복사되어 전달된다.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass


@dataclass(slots=True)
class RequestInfo:
    method: str
    path: str
    full_path: str
    member_id: int | None
    remote_addr: str | None
    endpoint: str | None = None


current_request: ContextVar[RequestInfo | None] = ContextVar("current_request", default=None)


def request_member_id() -> int | None:
    info = current_request.get()
    return info.member_id if info else None


def request_path(default: str = "CLI/background") -> str:
    info = current_request.get()
    return info.path if info else default
