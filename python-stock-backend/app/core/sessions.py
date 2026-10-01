"""서버 측(Redis) 로그인 세션 미들웨어.

Flask-Session과 같은 모델을 유지한다: 브라우저 쿠키에는 서명된 세션 ID만 두고, 실제 데이터는
``{prefix}{sid}`` 키로 Redis에 JSON으로 저장한다. 라우트는 ``request.session``(dict)으로 접근하며
변경이 있을 때만 저장하고, 로그인 직후에는 ``request.session.regenerate()``로 ID를 교체해 세션 고정을 막는다.
"""

from __future__ import annotations

import json
import secrets
import time
from http.cookies import SimpleCookie
from typing import Any, Protocol

from itsdangerous import BadSignature, Signer
from starlette.datastructures import MutableHeaders
from starlette.requests import cookie_parser
from starlette.types import ASGIApp, Message, Receive, Scope, Send

_SALT = "stock-coin-trade.session"


class SessionData(dict[str, Any]):
    """요청 동안 살아 있는 세션 사전. 쓰기 연산을 추적해 변경이 있을 때만 저장한다."""

    def __init__(self, data: dict[str, Any] | None, sid: str | None):
        super().__init__(data or {})
        self.sid = sid
        self.modified = False
        self._regenerate = False

    def _touch(self) -> None:
        self.modified = True

    def __setitem__(self, key: str, value: Any) -> None:
        super().__setitem__(key, value)
        self._touch()

    def __delitem__(self, key: str) -> None:
        super().__delitem__(key)
        self._touch()

    def clear(self) -> None:
        super().clear()
        self._touch()

    def pop(self, key: str, *default: Any) -> Any:
        self._touch()
        return super().pop(key, *default)

    def update(self, *args: Any, **kwargs: Any) -> None:
        super().update(*args, **kwargs)
        self._touch()

    def setdefault(self, key: str, default: Any = None) -> Any:
        if key not in self:
            self._touch()
        return super().setdefault(key, default)

    def regenerate(self) -> None:
        """다음 응답에서 새 세션 ID를 발급한다(로그인·권한 상승 직후 호출)."""
        self._regenerate = True
        self._touch()

    @property
    def needs_new_id(self) -> bool:
        return self._regenerate or self.sid is None


class SessionStore(Protocol):
    async def load(self, sid: str) -> dict[str, Any] | None: ...

    async def save(self, sid: str, data: dict[str, Any], ttl: int) -> None: ...

    async def touch(self, sid: str, ttl: int) -> None: ...

    async def delete(self, sid: str) -> None: ...


class RedisSessionStore:
    def __init__(self, url: str, prefix: str):
        from redis.asyncio import Redis

        self._redis = Redis.from_url(url, socket_connect_timeout=3, socket_timeout=3)
        self._prefix = prefix

    def _key(self, sid: str) -> str:
        return f"{self._prefix}{sid}"

    async def load(self, sid: str) -> dict[str, Any] | None:
        raw = await self._redis.get(self._key(sid))
        if raw is None:
            return None
        try:
            data = json.loads(raw)
        except ValueError:
            return None
        return data if isinstance(data, dict) else None

    async def save(self, sid: str, data: dict[str, Any], ttl: int) -> None:
        await self._redis.set(self._key(sid), json.dumps(data, ensure_ascii=False, default=str), ex=ttl)

    async def touch(self, sid: str, ttl: int) -> None:
        await self._redis.expire(self._key(sid), ttl)

    async def delete(self, sid: str) -> None:
        await self._redis.delete(self._key(sid))


class MemorySessionStore:
    """Redis 없는 로컬 개발·테스트용. 프로세스가 끝나면 세션도 사라진다."""

    def __init__(self) -> None:
        self.data: dict[str, tuple[float, dict[str, Any]]] = {}

    async def load(self, sid: str) -> dict[str, Any] | None:
        entry = self.data.get(sid)
        if not entry:
            return None
        expires_at, payload = entry
        if expires_at < time.time():
            self.data.pop(sid, None)
            return None
        return dict(payload)

    async def save(self, sid: str, data: dict[str, Any], ttl: int) -> None:
        self.data[sid] = (time.time() + ttl, dict(data))

    async def touch(self, sid: str, ttl: int) -> None:
        if sid in self.data:
            self.data[sid] = (time.time() + ttl, self.data[sid][1])

    async def delete(self, sid: str) -> None:
        self.data.pop(sid, None)


def session_signer(secret_key: str) -> Signer:
    return Signer(secret_key, salt=_SALT)


class ServerSessionMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        *,
        store: SessionStore,
        secret_key: str,
        cookie_name: str = "session",
        max_age: int = 7 * 86_400,
        same_site: str = "lax",
        https_only: bool = False,
    ) -> None:
        self.app = app
        self.store = store
        self.signer = session_signer(secret_key)
        self.cookie_name = cookie_name
        self.max_age = max_age
        self.same_site = same_site
        self.https_only = https_only

    def sign(self, sid: str) -> str:
        return self.signer.sign(sid.encode()).decode()

    def _unsign(self, value: str | None) -> str | None:
        if not value:
            return None
        try:
            return self.signer.unsign(value.encode()).decode()
        except (BadSignature, UnicodeDecodeError):
            return None

    def _cookie(self, value: str, max_age: int) -> str:
        cookie: SimpleCookie = SimpleCookie()
        cookie[self.cookie_name] = value
        morsel = cookie[self.cookie_name]
        morsel["path"] = "/"
        morsel["httponly"] = True
        morsel["samesite"] = self.same_site.capitalize()
        morsel["max-age"] = max_age
        if max_age <= 0:
            morsel["expires"] = "Thu, 01 Jan 1970 00:00:00 GMT"
        if self.https_only:
            morsel["secure"] = True
        return morsel.OutputString()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        raw_cookie = next((value.decode("latin-1") for key, value in scope["headers"] if key == b"cookie"), "")
        cookies = cookie_parser(raw_cookie) if raw_cookie else {}
        had_cookie = self.cookie_name in cookies
        sid = self._unsign(cookies.get(self.cookie_name))
        data = await self.store.load(sid) if sid else None
        if data is None:
            sid = None
        session = SessionData(data, sid)
        scope["session"] = session

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                await self._persist(session, message, had_cookie)
            await send(message)

        await self.app(scope, receive, send_wrapper)

    async def _persist(self, session: SessionData, message: Message, had_cookie: bool) -> None:
        headers = MutableHeaders(scope=message)
        if not session.modified:
            if session.sid:
                await self.store.touch(session.sid, self.max_age)
            return
        old_sid = session.sid
        if not session:
            if old_sid:
                await self.store.delete(old_sid)
            if old_sid or had_cookie:
                headers.append("set-cookie", self._cookie("", 0))
            return
        sid = old_sid
        if session.needs_new_id:
            sid = secrets.token_urlsafe(32)
            if old_sid:
                await self.store.delete(old_sid)
        await self.store.save(sid, dict(session), self.max_age)
        headers.append("set-cookie", self._cookie(self.sign(sid), self.max_age))
