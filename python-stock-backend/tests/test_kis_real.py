from unittest.mock import patch

from tests.conftest import CSRF_TOKEN


def test_status_requires_separate_real_configuration(client, login):
    login()
    with patch.dict("os.environ", {}, clear=True):
        response = client.get("/api/kis-real/status")
    assert response.status_code == 200
    body = response.json()
    assert body["ready"] is False
    assert body["configured"]["appKey"] is False
    assert body["environment"] == "KIS 실전투자"


def test_status_requires_login(client):
    response = client.get("/api/kis-real/status")
    assert response.status_code == 401
    assert response.json() == {"ok": False, "error": "UNAUTHORIZED", "message": "로그인이 필요합니다."}


def test_balance_requires_csrf(client, login):
    login()
    response = client.post("/api/kis-real/balance", json={})
    assert response.status_code == 403
    assert response.json()["error"] == "CSRF_INVALID"


@patch("app.services.brokers.kis_real.requests.post")
def test_missing_real_configuration_never_calls_kis(token_request, client, login):
    login()
    with patch.dict("os.environ", {}, clear=True), patch("app.api.routes.kis_real.member_email", return_value="owner@example.com"):
        response = client.post("/api/kis-real/balance", json={}, headers={"X-CSRF-Token": CSRF_TOKEN})
    assert response.status_code == 503
    assert response.json()["error"] == "REAL_CONFIG_REQUIRED"
    token_request.assert_not_called()


@patch("app.api.routes.kis_real.member_email", return_value="owner@example.com")
@patch("app.api.routes.kis_real.get_real_balance")
def test_authorized_balance_response_is_read_only(get_balance, _email, client, login):
    login()
    get_balance.return_value = {
        "cashBalance": "10000", "totalEvalAmount": "12000", "totalProfitLoss": "2000",
        "holdingsCount": 0, "holdings": [], "environment": "KIS 실전투자", "readOnly": True,
    }
    response = client.post("/api/kis-real/balance", json={}, headers={"X-CSRF-Token": CSRF_TOKEN})
    assert response.status_code == 200
    assert response.json()["balance"]["readOnly"] is True
    get_balance.assert_called_once()
    assert get_balance.call_args.args[0]() == "owner@example.com"

