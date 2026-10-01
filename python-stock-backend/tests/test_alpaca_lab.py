from unittest.mock import Mock, patch

from app.services.alpaca import paper as alpaca


def test_status_requires_login(client):
    response = client.get("/api/alpaca-test/status")
    assert response.status_code == 401


@patch("app.api.routes.alpaca_test.get_alpaca_configuration_status")
def test_status_contains_no_credentials(status, client, login):
    status.return_value = {
        "configured": True, "source": "environment", "environment": {"complete": True},
        "tradingEndpoint": alpaca.ALPACA_PAPER_BASE, "dataEndpoint": alpaca.ALPACA_DATA_BASE,
        "mode": "paper", "liveEnabled": False,
    }
    login(csrf_token=None)
    response = client.get("/api/alpaca-test/status")
    assert response.status_code == 200
    body = response.json()
    assert body["status"]["configured"] is True
    assert "secret-value" not in str(body)


@patch("app.services.alpaca.paper._audit_alpaca_call")
@patch("app.services.alpaca.paper._headers", return_value={})
@patch("app.services.alpaca.paper.requests.get")
def test_read_call_is_audited_without_account_identifier(request_call, _headers, audit):
    response = Mock(status_code=200, ok=True)
    response.json.return_value = {"id": "account-secret-id", "account_number": "123456", "status": "ACTIVE"}
    request_call.return_value = response
    result = alpaca._get(f"{alpaca.ALPACA_PAPER_BASE}/account")
    assert result["status"] == "ACTIVE"
    logged = str(audit.call_args.kwargs["response_body"])
    assert "account-secret-id" not in logged
    assert "123456" not in logged
    assert audit.call_args.kwargs["success"] is True
