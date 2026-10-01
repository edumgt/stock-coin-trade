"""세션에 결합된 CSRF 토큰(상태 변경 JSON API용)."""

from __future__ import annotations

import hmac
import secrets

from fastapi import Request

CSRF_SESSION_KEY = "csrf_token"
CSRF_HEADER = "X-CSRF-Token"


def csrf_token(request: Request) -> str:
    token = request.session.get(CSRF_SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        request.session[CSRF_SESSION_KEY] = token
    return token


def csrf_is_valid(request: Request) -> bool:
    expected = request.session.get(CSRF_SESSION_KEY)
    supplied = request.headers.get(CSRF_HEADER, "")
    return bool(expected and supplied and hmac.compare_digest(expected, supplied))
