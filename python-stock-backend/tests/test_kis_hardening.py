from unittest.mock import Mock, patch

from app.services import api_usage
from app.services.brokers import kis as broker
from tests.conftest import CSRF_TOKEN


@patch("app.api.routes.broker_test.get_kis_balance")
@patch("app.api.routes.broker_test.can_use_kis_account", return_value=False)
def test_balance_requires_login(_access, get_balance, client, login):
    login()
    response = client.get("/api/broker-test/kis/balance")
    assert response.status_code == 401
    get_balance.assert_not_called()


def test_invalid_symbol_is_http_400(client):
    response = client.get("/api/broker-test/kis/quote?symbol=ABC")
    assert response.status_code == 400
    assert response.json()["ok"] is False


def test_non_paper_environment_is_rejected():
    with patch.dict("os.environ", {"KIS_ENVIRONMENT": "real"}):
        try:
            broker._kis_credentials()
        except broker.BrokerApiError as caught:
            assert caught.status_code == 503
        else:
            raise AssertionError("BrokerApiError expected")


@patch("app.services.brokers.kis.kis_request")
def test_quote_cache_has_a_hard_size_limit(kis_request):
    kis_request.return_value = (Mock(status_code=200), {"output": {"stck_prpr": "1000"}})
    with broker._kis_quote_lock:
        broker._kis_quote_cache.clear()
    for number in range(broker._KIS_QUOTE_CACHE_MAX + 1):
        broker.get_kis_quote(f"{number:06d}")
    assert len(broker._kis_quote_cache) == broker._KIS_QUOTE_CACHE_MAX


def test_gateway_masks_credentials_and_account():
    safe = api_usage._safe_value({
        "appkey": "secret-key", "appsecret": "secret-value", "CANO": "12345678",
        "nested": {"access_token": "token-value", "symbol": "005930"},
    })
    assert safe["appkey"] == "***"
    assert safe["appsecret"] == "***"
    assert safe["CANO"] == "1234****"
    assert safe["nested"]["access_token"] == "***"
    assert safe["nested"]["symbol"] == "005930"


@patch("app.services.brokers.kis.time.sleep")
@patch("app.services.brokers.kis._audit_kis_call")
@patch("app.services.brokers.kis._kis_headers", return_value={})
@patch("app.services.brokers.kis.requests.request")
def test_each_gateway_retry_is_audited(request_call, _headers, audit, _sleep):
    rate_limited = Mock(status_code=200)
    rate_limited.json.return_value = {"rt_cd": "1", "msg_cd": "EGW00201", "msg1": "rate limit"}
    succeeded = Mock(status_code=200)
    succeeded.json.return_value = {"rt_cd": "0", "msg_cd": "", "msg1": "success"}
    request_call.side_effect = [rate_limited, succeeded]
    with patch.object(broker, "_KIS_API_CALL_GAP_SECONDS", 0):
        _, body = broker.kis_request("GET", "/uapi/test", "TEST001", params={"symbol": "005930"}, label="테스트")
    assert body["rt_cd"] == "0"
    assert audit.call_count == 2
    assert audit.call_args_list[0].kwargs["success"] is False
    assert audit.call_args_list[1].kwargs["success"] is True
    assert audit.call_args_list[1].kwargs["attempt"] == 2


def test_invalid_chart_count_is_http_400(client):
    response = client.get("/api/kis-chart/candles?symbol=005930&count=bad")
    assert response.status_code == 400
    assert response.json()["ok"] is False


def test_explorer_call_requires_csrf(client, login):
    login()
    response = client.post("/api/kis-explorer/call", json={"id": "inquire_price", "params": {}})
    assert response.status_code == 403


@patch("app.api.routes.kis_explorer.can_use_kis_account", return_value=False)
def test_explorer_account_api_requires_login(_access, client, login):
    login()
    response = client.post(
        "/api/kis-explorer/call",
        json={"id": "inquire_daily_ccld", "params": {}},
        headers={"X-CSRF-Token": CSRF_TOKEN},
    )
    assert response.status_code == 401


@patch("app.api.routes.broker_test.can_use_kis_account", return_value=True)
def test_order_approval_requires_csrf(_access, client, login):
    login()
    response = client.post("/api/broker-test/kis/order-flow-approval", json={})
    assert response.status_code == 403


@patch("app.api.routes.broker_test.run_kis_mock_order_flow_test", return_value={"order": "success"})
@patch("app.api.routes.broker_test.can_use_kis_account", return_value=True)
def test_order_approval_is_single_use(_access, run_flow, client, login):
    login()
    headers = {"X-CSRF-Token": CSRF_TOKEN}
    approval_response = client.post("/api/broker-test/kis/order-flow-approval", json={}, headers=headers)
    assert approval_response.status_code == 200
    approval = approval_response.json()["approvalToken"]

    first = client.post("/api/broker-test/kis/order-flow-test", json={"approvalToken": approval}, headers=headers)
    assert first.status_code == 200
    assert first.json()["ok"] is True
    run_flow.assert_called_once()

    replay = client.post("/api/broker-test/kis/order-flow-test", json={"approvalToken": approval}, headers=headers)
    assert replay.status_code == 403
    run_flow.assert_called_once()


@patch("app.api.routes.broker_test.place_kis_paper_order", return_value={"orderNo": "123", "environment": "paper"})
@patch("app.api.routes.broker_test.can_use_kis_account", return_value=True)
def test_paper_order_approval_binds_exact_intent_and_is_single_use(_access, place_order, client, login):
    login()
    headers = {"X-CSRF-Token": CSRF_TOKEN}
    intent = {"symbol": "005930", "side": "BUY", "quantity": 1, "orderType": "MARKET", "price": 0}
    approval_response = client.post("/api/broker-test/kis/order-approval", json=intent, headers=headers)
    assert approval_response.status_code == 200
    token = approval_response.json()["approvalToken"]

    tampered = client.post("/api/broker-test/kis/orders", json={**intent, "quantity": 2, "approvalToken": token}, headers=headers)
    assert tampered.status_code == 403
    place_order.assert_not_called()

    second_approval = client.post("/api/broker-test/kis/order-approval", json=intent, headers=headers).json()["approvalToken"]
    accepted = client.post("/api/broker-test/kis/orders", json={**intent, "approvalToken": second_approval}, headers=headers)
    assert accepted.status_code == 200
    place_order.assert_called_once_with("005930", "BUY", 1, "MARKET", 0)

    replay = client.post("/api/broker-test/kis/orders", json={**intent, "approvalToken": second_approval}, headers=headers)
    assert replay.status_code == 403
    place_order.assert_called_once()


@patch("app.services.brokers.kis.get_kis_balance", return_value={"cashBalance": "1000000", "holdings": []})
@patch("app.services.brokers.kis.get_kis_quote", return_value={"price": "70000"})
@patch("app.services.brokers.kis._kis_order_post", return_value={"rt_cd": "0", "msg1": "접수", "output": {"ODNO": "77"}})
@patch("app.services.brokers.kis._kis_account", return_value=("12345678", "01"))
def test_general_paper_order_uses_testbed_buy_tr_id(_account, order_post, _quote, _balance):
    result = broker.place_kis_paper_order("005930", "BUY", 1, "MARKET", 0)
    assert result["environment"] == "paper"
    assert result["orderNo"] == "77"
    assert order_post.call_args.args[1] == "VTTC0012U"
    assert order_post.call_args.args[2]["ORD_DVSN"] == "01"
