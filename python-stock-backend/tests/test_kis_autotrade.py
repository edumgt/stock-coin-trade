"""KIS 자동매매 Open API (/openapi/v1/kis): 스코프·승인 토큰·멱등성·환경 분리·상태 정규화.

KIS 실호출은 전부 kis_autotrade.request / get_balance / _account 를 패치해 막는다. DB는 SQLite 메모리.
"""

from unittest.mock import Mock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import get_db
from app.models import Base, KisAutotradeOrder, KisOrderApproval
from app.services.brokers import kis as paper_gateway
from app.services.brokers import kis_autotrade as svc

AUTH = {"Authorization": "Bearer test-key"}
ORDER = {"environment": "paper", "symbol": "005930", "side": "BUY", "orderType": "LIMIT", "quantity": 2, "price": 70000, "clientOrderId": "u1:005930:BUY:1"}
KIS_OK = {"rt_cd": "0", "msg_cd": "APBK0013", "msg1": "주문 전송 완료", "output": {"ODNO": "0000001234", "KRX_FWDG_ORD_ORGNO": "91252", "ORD_TMD": "103105"}}


@pytest.fixture
def db_session_factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[KisOrderApproval.__table__, KisAutotradeOrder.__table__])
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture
def api(app, client, db_session_factory, monkeypatch):
    """API 키(id=5, member=7)가 화이트리스트에 있고, KIS 호출이 모두 가짜인 클라이언트."""

    def _get_db():
        db = db_session_factory()
        try:
            yield db
            db.commit()
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_db
    monkeypatch.setenv("KIS_AUTOTRADE_API_KEY_IDS", "5")
    monkeypatch.delenv("KIS_REAL_ORDER_ENABLED", raising=False)
    with patch("app.api.routes.openapi.resolve_api_key", return_value=(5, 7)), \
         patch.object(svc, "_account", return_value=("12345678", "01")), \
         patch.object(svc, "get_balance", return_value={"cashBalance": 10_000_000, "holdings": [{"symbol": "005930", "quantity": 10}]}), \
         patch.object(svc, "request", return_value=(Mock(status_code=200), KIS_OK)) as kis_request:
        client.kis_request = kis_request
        client.db = db_session_factory
        yield client


def _approve(api, body=ORDER):
    response = api.post("/openapi/v1/kis/order-approval", json=body, headers=AUTH)
    assert response.status_code == 200, response.text
    return response.json()["approvalToken"]


def test_scope_is_deny_by_default(api, monkeypatch):
    monkeypatch.setenv("KIS_AUTOTRADE_API_KEY_IDS", "")
    response = api.post("/openapi/v1/kis/order-approval", json=ORDER, headers=AUTH)
    assert response.status_code == 403
    assert response.json()["error"] == "SCOPE_FORBIDDEN"


def test_order_requires_api_key(client):
    response = client.post("/openapi/v1/kis/orders", json=ORDER)
    assert response.status_code == 401


def test_approval_then_order_records_accepted(api):
    token = _approve(api)
    response = api.post("/openapi/v1/kis/orders", json={**ORDER, "approvalToken": token}, headers=AUTH)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["duplicate"] is False
    assert body["order"]["status"] == "ACCEPTED"
    assert body["order"]["orderNo"] == "0000001234"
    assert body["order"]["orgNo"] == "91252"
    assert body["order"]["estimatedAmount"] == 140000
    call = api.kis_request.call_args
    assert call.args[:2] == ("paper", "POST") and call.args[3] == "order_buy"
    assert call.kwargs["payload"]["ORD_DVSN"] == "00" and call.kwargs["payload"]["ORD_QTY"] == "2"
    with api.db() as db:
        row = db.query(KisAutotradeOrder).one()
        assert row.status == "ACCEPTED" and row.client_order_id == ORDER["clientOrderId"]
        assert "12345678" not in (row.request_json or "")  # 계좌번호 마스킹


def test_approval_token_is_single_use_and_bound_to_intent(api):
    token = _approve(api)
    changed = {**ORDER, "quantity": 3, "approvalToken": token}
    response = api.post("/openapi/v1/kis/orders", json=changed, headers=AUTH)
    assert response.status_code == 403 and response.json()["error"] == "APPROVAL_INVALID"
    assert api.kis_request.call_count == 0

    ok = api.post("/openapi/v1/kis/orders", json={**ORDER, "approvalToken": token}, headers=AUTH)
    assert ok.status_code == 200
    reused = api.post("/openapi/v1/kis/orders", json={**ORDER, "approvalToken": token}, headers=AUTH)
    assert reused.status_code == 403 and reused.json()["error"] == "APPROVAL_INVALID"
    assert api.kis_request.call_count == 1


def test_duplicate_client_order_id_never_reorders(api):
    api.post("/openapi/v1/kis/orders", json={**ORDER, "approvalToken": _approve(api)}, headers=AUTH)
    again = api.post("/openapi/v1/kis/orders", json={**ORDER, "approvalToken": _approve(api)}, headers=AUTH)
    assert again.status_code == 200
    assert again.json()["duplicate"] is True
    assert again.json()["order"]["orderNo"] == "0000001234"
    assert api.kis_request.call_count == 1


def test_kis_rejection_is_recorded_and_502(api):
    api.kis_request.return_value = (Mock(status_code=200), {"rt_cd": "1", "msg_cd": "APBK0919", "msg1": "주문가능금액 부족", "output": {}})
    response = api.post("/openapi/v1/kis/orders", json={**ORDER, "approvalToken": _approve(api)}, headers=AUTH)
    assert response.status_code == 502
    assert response.json()["error"] == "KIS_APBK0919"
    with api.db() as db:
        assert db.query(KisAutotradeOrder).one().status == "REJECTED"


def test_real_environment_is_rejected_without_server_flag(api):
    response = api.post("/openapi/v1/kis/order-approval", json={**ORDER, "environment": "real"}, headers=AUTH)
    assert response.status_code == 403
    assert response.json()["error"] == "REAL_ORDER_DISABLED"


def test_real_environment_requires_owner_email(api, monkeypatch):
    monkeypatch.setenv("KIS_REAL_ORDER_ENABLED", "true")
    monkeypatch.setenv("KIS_REAL_OWNER_EMAIL", "owner@example.com")
    with patch("app.api.routes.openapi_kis.member_email", return_value="someone@example.com"):
        denied = api.post("/openapi/v1/kis/order-approval", json={**ORDER, "environment": "real"}, headers=AUTH)
    assert denied.status_code == 403
    with patch("app.api.routes.openapi_kis.member_email", return_value="owner@example.com"):
        allowed = api.post("/openapi/v1/kis/order-approval", json={**ORDER, "environment": "real"}, headers=AUTH)
    assert allowed.status_code == 200


def test_per_order_limits(api, monkeypatch):
    monkeypatch.setenv("KIS_PAPER_MAX_ORDER_AMOUNT", "100000")
    response = api.post("/openapi/v1/kis/orders", json={**ORDER, "approvalToken": _approve(api)}, headers=AUTH)
    assert response.status_code == 422 and response.json()["error"] == "LIMIT_EXCEEDED"
    assert api.kis_request.call_count == 0


def test_invalid_intent_messages():
    with pytest.raises(svc.AutotradeError) as bad_symbol:
        svc.normalize_intent({**ORDER, "symbol": "AAPL"})
    assert bad_symbol.value.code == "INVALID_REQUEST"
    with pytest.raises(svc.AutotradeError):
        svc.normalize_intent({**ORDER, "price": 70001})  # 호가 단위 위반
    with pytest.raises(svc.AutotradeError):
        svc.normalize_intent({**ORDER, "clientOrderId": ""})
    market = svc.normalize_intent({**ORDER, "orderType": "market", "price": 123})
    assert market["price"] == 0 and market["orderType"] == "MARKET"


def test_tr_id_mapping_paper_vs_real():
    assert svc.tr_id("order_buy", "paper") == "VTTC0012U" and svc.tr_id("order_buy", "real") == "TTTC0012U"
    assert svc.tr_id("order_sell", "real") == "TTTC0011U"
    assert svc.tr_id("daily_ccld", "real") == "TTTC8001R"
    assert svc.tr_id("order_rvsecncl", "paper") == "VTTC0013U"


def test_real_request_uses_real_base_url_and_headers(monkeypatch):
    monkeypatch.setenv("KIS_REAL_APP_KEY", "real-key")
    monkeypatch.setenv("KIS_REAL_APP_SECRET", "real-secret")
    monkeypatch.setenv("KIS_REAL_ACCOUNT_NO", "12345678-01")
    monkeypatch.delenv("CREDENTIAL_SOURCE", raising=False)
    with patch.object(paper_gateway, "kis_request", return_value=(Mock(), {"rt_cd": "0"})) as gateway, \
         patch.object(svc.kis_real, "_access_token", return_value="tok"):
        svc.request("real", "GET", "/uapi/x", "balance", label="테스트")
        kwargs = gateway.call_args.kwargs
        assert gateway.call_args.args[2] == "TTTC8434R"
        assert kwargs["base_url"] == svc.KIS_REAL_BASE_URL
        headers = kwargs["headers_factory"]("TTTC8434R")
        assert headers["appkey"] == "real-key" and headers["authorization"] == "Bearer tok"

        svc.request("paper", "GET", "/uapi/x", "balance", label="테스트")
        assert gateway.call_args.args[2] == "VTTC8434R"
        assert "base_url" not in gateway.call_args.kwargs


def test_status_normalization_from_daily_ccld():
    assert svc._status_from_ccld({"ord_qty": "3", "tot_ccld_qty": "3", "rmn_qty": "0"}) == "FILLED"
    assert svc._status_from_ccld({"ord_qty": "3", "tot_ccld_qty": "1", "rmn_qty": "2"}) == "PARTIALLY_FILLED"
    assert svc._status_from_ccld({"ord_qty": "3", "tot_ccld_qty": "0", "rmn_qty": "3"}) == "ACCEPTED"
    assert svc._status_from_ccld({"ord_qty": "3", "tot_ccld_qty": "0", "rmn_qty": "0", "cncl_cfrm_qty": "3"}) == "CANCELLED"
    assert svc._status_from_ccld({"ord_qty": "3", "tot_ccld_qty": "0", "rmn_qty": "0", "rjct_qty": "3"}) == "REJECTED"


def test_order_status_endpoint_updates_record(api):
    api.post("/openapi/v1/kis/orders", json={**ORDER, "approvalToken": _approve(api)}, headers=AUTH)
    api.kis_request.return_value = (Mock(status_code=200), {"rt_cd": "0", "output1": [
        {"odno": "0000001234", "pdno": "005930", "prdt_name": "삼성전자", "sll_buy_dvsn_cd": "02", "ord_qty": "2",
         "tot_ccld_qty": "2", "rmn_qty": "0", "ord_unpr": "70000", "avg_prvs": "69900", "ord_tmd": "103140", "ord_gno_brno": "91252"},
    ]})
    response = api.get("/openapi/v1/kis/orders/0000001234?environment=paper", headers=AUTH)
    assert response.status_code == 200, response.text
    order = response.json()["order"]
    assert order["status"] == "FILLED" and order["filledQuantity"] == 2 and order["clientOrderId"] == ORDER["clientOrderId"]
    with api.db() as db:
        row = db.query(KisAutotradeOrder).one()
        assert row.status == "FILLED" and row.avg_filled_price == 69900


# ── 2차 작업: api_key.scopes 우선, 연속조회 페이지네이션, 생성일 기준 조회 범위 ──────────────
from datetime import datetime, timedelta  # noqa: E402

from app.models import ApiKey  # noqa: E402


def test_scopes_column_grants_access_without_env_whitelist(api, monkeypatch):
    monkeypatch.setenv("KIS_AUTOTRADE_API_KEY_IDS", "")
    Base.metadata.create_all(api.db.kw["bind"], tables=[ApiKey.__table__])
    with api.db() as db:
        db.add(ApiKey(api_key_id=5, member_id=7, label="bot", key_prefix="eduapi_live_abcd", key_hash="h" * 64, scopes="kis:read, kis:order"))
        db.commit()
    response = api.post("/openapi/v1/kis/order-approval", json=ORDER, headers=AUTH)
    assert response.status_code == 200, response.text
    with api.db() as db:
        db.get(ApiKey, 5).scopes = "kis:read"
        db.commit()
    denied = api.post("/openapi/v1/kis/order-approval", json=ORDER, headers=AUTH)
    assert denied.status_code == 403 and denied.json()["error"] == "SCOPE_FORBIDDEN"


def test_list_orders_follows_kis_continuation_pages(api):
    page1 = Mock(status_code=200, headers={"tr_cont": "M"})
    page2 = Mock(status_code=200, headers={"tr_cont": "D"})
    row = {"odno": "1", "pdno": "005930", "sll_buy_dvsn_cd": "02", "ord_qty": "1", "tot_ccld_qty": "1", "rmn_qty": "0"}
    api.kis_request.side_effect = [
        (page1, {"rt_cd": "0", "output1": [row], "ctx_area_fk100": "FK1", "ctx_area_nk100": "NK1"}),
        (page2, {"rt_cd": "0", "output1": [{**row, "odno": "2"}]}),
    ]
    orders = svc.list_orders("paper", "20261001", "20261002")
    assert [o["orderNo"] for o in orders] == ["1", "2"]
    assert api.kis_request.call_count == 2
    second = api.kis_request.call_args_list[1]
    assert second.kwargs["extra_headers"]["tr_cont"] == "N"
    assert second.kwargs["params"]["CTX_AREA_FK100"] == "FK1" and second.kwargs["params"]["CTX_AREA_NK100"] == "NK1"
    assert second.kwargs["params"]["INQR_STRT_DT"] == "20261001"


def test_sync_order_status_queries_from_order_creation_date(api):
    api.post("/openapi/v1/kis/orders", json={**ORDER, "approvalToken": _approve(api)}, headers=AUTH)
    with api.db() as db:
        rec = db.query(KisAutotradeOrder).one()
        rec.created_at = datetime.now() - timedelta(days=2)
        db.commit()
    api.kis_request.return_value = (Mock(status_code=200, headers={}), {"rt_cd": "0", "output1": []})
    response = api.get("/openapi/v1/kis/orders/0000001234?environment=paper", headers=AUTH)
    assert response.status_code == 200
    assert response.json()["order"]["lookup"] == "not_in_daily_ccld"
    params = api.kis_request.call_args.kwargs["params"]
    assert params["INQR_STRT_DT"] == (datetime.now() - timedelta(days=2)).strftime("%Y%m%d")
    assert params["INQR_END_DT"] == datetime.now().strftime("%Y%m%d")
