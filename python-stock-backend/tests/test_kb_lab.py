from unittest.mock import Mock, patch

import pytest

from app.services.brokers import kb as broker


def test_kb_status_requires_login(client):
    response = client.get("/api/broker-test/kb/status")
    assert response.status_code == 401


@patch("app.api.routes.broker_test.get_kb_configuration_status")
def test_kb_status_returns_no_secret_values(status, client, login):
    status.return_value = {
        "configured": True, "source": "environment", "environment": {"complete": True},
        "endpoint": broker.KB_API_BASE_URL, "mode": "production", "readOnly": True,
    }
    login(csrf_token=None)
    response = client.get("/api/broker-test/kb/status")
    assert response.status_code == 200
    body = response.json()
    assert body["status"]["configured"] is True
    assert "appSecret" not in str(body)


@patch("app.services.brokers.kb._audit_kb_call")
@patch("app.services.brokers.kb._kb_data_header", return_value={})
@patch("app.services.brokers.kb._credentials", return_value=("key", "secret"))
@patch("app.services.brokers.kb._kb_token_response", return_value={"access_token": "token"})
@patch("app.services.brokers.kb.requests.post")
def test_business_error_on_http_200_is_rejected_and_audited(request_call, _token, _credentials, _header, audit):
    response = Mock(status_code=200, ok=True)
    response.json.return_value = {"dataHeader": {"processCode": "E123", "processMessage": "권한 없음"}, "dataBody": {}}
    request_call.return_value = response
    with pytest.raises(broker.BrokerApiError):
        broker._kb_investment_info("/api/v1/ivu10140", {"shrt_cd": "005930"})
    assert audit.call_args.kwargs["success"] is False


@patch("app.services.brokers.kb._audit_kb_call")
@patch("app.services.brokers.kb._kb_data_header", return_value={})
@patch("app.services.brokers.kb._credentials", return_value=("key", "secret"))
@patch("app.services.brokers.kb._kb_token_response", return_value={"access_token": "token"})
@patch("app.services.brokers.kb.requests.post")
def test_process_code_0024_is_normal_completion(request_call, _token, _credentials, _header, audit):
    response = Mock(status_code=200, ok=True)
    response.json.return_value = {
        "dataHeader": {"processCode": "0024", "processMessage": "정상적으로 조회가 완료되었습니다."},
        "dataBody": {"out2": []},
    }
    request_call.return_value = response
    result = broker._kb_investment_info("/api/v1/ivs11560", {})
    assert result == {"out2": []}
    assert audit.call_args.kwargs["success"] is True


@patch("app.services.brokers.kb._kb_investment_info")
def test_chart_normalizes_official_ivs11560_fields(call):
    broker._kb_chart_cache.clear()
    call.return_value = {"out2": [
        {"dt": "20260918", "opn_prc_p2": " 261000", "hgh_prc_p2": "262000",
         "lw_prc_p2": "257500", "cls_prc_p2": "260000", "vlm": "17489615", "dl_tw_amt": "455429100625"},
        {"dt": "20260917", "opn_prc_p2": " 250000", "hgh_prc_p2": "255000",
         "lw_prc_p2": "249000", "cls_prc_p2": "252500", "vlm": "100", "dl_tw_amt": "200"},
    ]}
    result = broker.get_kb_stock_chart("005930", "0", "D", 60)
    assert result["source"] == "IVS11560"
    assert result["count"] == 2
    assert result["candles"][0]["time"] == "2026-09-17"
    assert result["candles"][1]["close"] == 260000
    request_body = call.call_args.args[1]
    assert request_body["mkt_clsf"] == "0"
    assert request_body["inq_clsf"] == "2"
