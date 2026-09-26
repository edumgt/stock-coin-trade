import unittest
from unittest.mock import Mock, patch

from flask import Flask

import alpaca_test
from alpaca_test_api import alpaca_test_bp


class AlpacaLabTest(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.config.update(SECRET_KEY="test-secret", TESTING=True)
        app.register_blueprint(alpaca_test_bp)
        self.client = app.test_client()

    def login(self):
        with self.client.session_transaction() as sess:
            sess["member_id"] = 7

    def test_status_requires_login(self):
        response = self.client.get("/api/alpaca-test/status")
        self.assertEqual(response.status_code, 401)

    @patch("alpaca_test_api.get_alpaca_configuration_status")
    def test_status_contains_no_credentials(self, status):
        status.return_value = {
            "configured": True, "source": "environment", "environment": {"complete": True},
            "tradingEndpoint": alpaca_test.ALPACA_PAPER_BASE, "dataEndpoint": alpaca_test.ALPACA_DATA_BASE,
            "mode": "paper", "liveEnabled": False,
        }
        self.login()
        response = self.client.get("/api/alpaca-test/status")
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertTrue(body["status"]["configured"])
        self.assertNotIn("secret-value", str(body))

    @patch("alpaca_test._audit_alpaca_call")
    @patch("alpaca_test._headers", return_value={})
    @patch("alpaca_test.requests.get")
    def test_read_call_is_audited_without_account_identifier(self, request_call, _headers, audit):
        response = Mock(status_code=200, ok=True)
        response.json.return_value = {"id": "account-secret-id", "account_number": "123456", "status": "ACTIVE"}
        request_call.return_value = response
        result = alpaca_test._get(f"{alpaca_test.ALPACA_PAPER_BASE}/account")
        self.assertEqual(result["status"], "ACTIVE")
        logged = str(audit.call_args.kwargs["response_body"])
        self.assertNotIn("account-secret-id", logged)
        self.assertNotIn("123456", logged)
        self.assertTrue(audit.call_args.kwargs["success"])


if __name__ == "__main__":
    unittest.main()
