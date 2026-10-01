from unittest.mock import Mock, patch

from app.core.database import get_db
from app.models import KisPracticeAccount, KisPracticeOrder, KisPracticePosition
from app.services.kis_practice import PracticeOrderRejected
from tests.conftest import CSRF_TOKEN


def test_practice_ledger_uses_dedicated_tables():
    assert KisPracticeAccount.__tablename__ == "kis_practice_account"
    assert KisPracticePosition.__tablename__ == "kis_practice_position"
    assert KisPracticeOrder.__tablename__ == "kis_practice_order"


def test_order_requires_login(client):
    response = client.post("/api/kis-practice/orders", json={"symbol": "005930", "side": "BUY", "quantity": 1})
    assert response.status_code == 401
    assert response.json()["error"] == "UNAUTHORIZED"


def test_order_requires_csrf(client, login):
    login()
    response = client.post("/api/kis-practice/orders", json={"symbol": "005930", "side": "BUY", "quantity": 1})
    assert response.status_code == 403
    assert response.json()["error"] == "CSRF_INVALID"


@patch("app.api.routes.kis_practice.kis_practice.execute_order")
def test_insufficient_balance_returns_http_409(execute_order, app, client, login):
    login()
    fake_db = Mock()
    app.dependency_overrides[get_db] = lambda: fake_db
    execute_order.side_effect = PracticeOrderRejected(
        "INSUFFICIENT_BALANCE",
        "주문 가능 금액(예수금)이 부족합니다.",
        status_code=409,
        details={"availableCash": 10_000, "requiredAmount": 70_000, "shortageAmount": 60_000},
    )
    response = client.post(
        "/api/kis-practice/orders",
        json={"symbol": "005930", "side": "BUY", "quantity": 1},
        headers={"X-CSRF-Token": CSRF_TOKEN},
    )
    assert response.status_code == 409
    assert response.json() == {
        "error": "INSUFFICIENT_BALANCE",
        "message": "주문 가능 금액(예수금)이 부족합니다.",
        "availableCash": 10_000,
        "requiredAmount": 70_000,
        "shortageAmount": 60_000,
    }
    execute_order.assert_called_once_with(fake_db, 7, "005930", "BUY", 1)
