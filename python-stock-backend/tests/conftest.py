"""테스트 공통 픽스처.

- 앱은 기동 작업(테이블 보정·시드·스케줄러)을 끄고 메모리 세션 저장소로 만든다.
- ``login`` 헬퍼가 세션 저장소에 회원 세션을 직접 넣고 서명된 쿠키를 클라이언트에 심는다.
- DB가 필요한 라우트는 ``app.dependency_overrides[get_db]``로 가짜 세션을 주입한다.
"""

from __future__ import annotations

import os
import warnings
from collections.abc import Callable

import pytest

os.environ.setdefault("APP_STARTUP_TASKS", "false")
os.environ.setdefault("SESSION_STORE", "memory")
os.environ.setdefault("SECRET_KEY", "test-secret")

warnings.filterwarnings("ignore", category=DeprecationWarning)

from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.sessions import MemorySessionStore, session_signer  # noqa: E402
from app.main import create_app  # noqa: E402

CSRF_TOKEN = "csrf-test-token"


@pytest.fixture
def session_store() -> MemorySessionStore:
    return MemorySessionStore()


@pytest.fixture
def app(session_store):
    settings = get_settings().model_copy(update={"app_startup_tasks": False, "scheduler_enabled": False, "audit_enabled": False})
    application = create_app(settings, session_store=session_store)
    yield application
    application.dependency_overrides.clear()


@pytest.fixture
def client(app):
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def login(client, session_store, app) -> Callable[..., str]:
    """회원 세션을 만들고 CSRF 토큰을 돌려준다."""

    def _login(member_id: int = 7, csrf_token: str | None = CSRF_TOKEN) -> str | None:
        settings = app.state.settings
        sid = f"test-session-{member_id}"
        data = {"member_id": member_id}
        if csrf_token:
            data["csrf_token"] = csrf_token
        session_store.data[sid] = (float("inf"), data)
        signed = session_signer(settings.secret_key).sign(sid.encode()).decode()
        client.cookies.set(settings.session_cookie_name, signed)
        return csrf_token

    return _login
