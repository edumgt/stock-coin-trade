"""서버 세션 미들웨어·CSRF·로그인 흐름 테스트(DB는 가짜 세션으로 대체)."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.core.database import get_db


def test_me_is_anonymous_and_issues_csrf_cookie(app, client, session_store):
    app.dependency_overrides[get_db] = lambda: Mock()
    response = client.get("/api/member/me")
    assert response.status_code == 200
    body = response.json()
    assert body["loggedIn"] is False
    assert body["csrfToken"]
    assert app.state.settings.session_cookie_name in response.cookies
    assert len(session_store.data) == 1


def test_login_regenerates_session_and_logout_clears_it(app, client, session_store):
    member = SimpleNamespace(member_id=42, username="tester", asset=100)
    app.dependency_overrides[get_db] = lambda: Mock()
    with patch("app.api.routes.members.member_service.authenticate", return_value=member):
        response = client.post("/api/member/login", json={"email": "a@b.c", "password": "pw"})
    assert response.status_code == 200
    assert response.json() == {"username": "tester", "asset": 100}
    assert len(session_store.data) == 1
    stored = next(iter(session_store.data.values()))[1]
    assert stored["member_id"] == 42

    response = client.post("/api/member/logout")
    assert response.status_code == 200
    assert session_store.data == {}


def test_login_rejects_blank_credentials(app, client):
    app.dependency_overrides[get_db] = lambda: Mock()
    response = client.post("/api/member/login", json={"email": "", "password": ""})
    assert response.status_code == 400
    assert response.json() == {"error": "이메일과 비밀번호를 입력해주세요."}


def test_protected_router_requires_login(client):
    response = client.get("/api/stocks/account")
    assert response.status_code == 401
    assert response.json() == {"error": "UNAUTHORIZED", "message": "로그인이 필요합니다."}


def test_register_reports_field_errors(app, client):
    app.dependency_overrides[get_db] = lambda: Mock()
    response = client.post("/api/member/register", json={"username": "u", "email": "bad", "password": "p", "password2": "p"})
    assert response.status_code == 400
    assert response.json() == {"field": "email", "error": "올바른 이메일을 입력해주세요."}


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}
