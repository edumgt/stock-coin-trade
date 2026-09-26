import unittest
from unittest.mock import Mock, patch

from flask import Flask

from broker_test_api import broker_test_bp
import broker_test
import api_usage
from kis_api_explorer import kis_explorer_bp
from kis_chart_api import kis_chart_bp


class KisHardeningTest(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.config.update(SECRET_KEY="test-secret", TESTING=True)
        app.register_blueprint(broker_test_bp)
        app.register_blueprint(kis_chart_bp)
        app.register_blueprint(kis_explorer_bp)
        self.client = app.test_client()

    def _login_with_csrf(self, token="csrf-test-token"):
        with self.client.session_transaction() as sess:
            sess["member_id"] = 7
            sess["csrf_token"] = token
        return token

    @patch("broker_test_api.get_kis_balance")
    @patch("broker_test_api.can_use_kis_account", return_value=False)
    def test_balance_requires_login(self, _access, get_balance):
        self._login_with_csrf()
        response = self.client.get("/api/broker-test/kis/balance")
        self.assertEqual(response.status_code, 401)
        get_balance.assert_not_called()

    def test_invalid_symbol_is_http_400(self):
        response = self.client.get("/api/broker-test/kis/quote?symbol=ABC")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.get_json()["ok"])

    def test_non_paper_environment_is_rejected(self):
        with patch.dict("os.environ", {"KIS_ENVIRONMENT": "real"}):
            with self.assertRaises(broker_test.BrokerApiError) as caught:
                broker_test._kis_credentials()
        self.assertEqual(caught.exception.status_code, 503)

    @patch("broker_test.kis_request")
    def test_quote_cache_has_a_hard_size_limit(self, kis_request):
        kis_request.return_value = (Mock(status_code=200), {"output": {"stck_prpr": "1000"}})
        with broker_test._kis_quote_lock:
            broker_test._kis_quote_cache.clear()
        for number in range(broker_test._KIS_QUOTE_CACHE_MAX + 1):
            broker_test.get_kis_quote(f"{number:06d}")
        self.assertEqual(len(broker_test._kis_quote_cache), broker_test._KIS_QUOTE_CACHE_MAX)

    def test_gateway_masks_credentials_and_account(self):
        safe = api_usage._safe_value({
            "appkey": "secret-key", "appsecret": "secret-value", "CANO": "12345678",
            "nested": {"access_token": "token-value", "symbol": "005930"},
        })
        self.assertEqual(safe["appkey"], "***")
        self.assertEqual(safe["appsecret"], "***")
        self.assertEqual(safe["CANO"], "1234****")
        self.assertEqual(safe["nested"]["access_token"], "***")
        self.assertEqual(safe["nested"]["symbol"], "005930")

    @patch("broker_test.time.sleep")
    @patch("broker_test._audit_kis_call")
    @patch("broker_test._kis_headers", return_value={})
    @patch("broker_test.requests.request")
    def test_each_gateway_retry_is_audited(self, request_call, _headers, audit, _sleep):
        rate_limited = Mock(status_code=200)
        rate_limited.json.return_value = {"rt_cd": "1", "msg_cd": "EGW00201", "msg1": "rate limit"}
        succeeded = Mock(status_code=200)
        succeeded.json.return_value = {"rt_cd": "0", "msg_cd": "", "msg1": "success"}
        request_call.side_effect = [rate_limited, succeeded]
        with patch.object(broker_test, "_KIS_API_CALL_GAP_SECONDS", 0):
            _, body = broker_test.kis_request(
                "GET", "/uapi/test", "TEST001", params={"symbol": "005930"}, label="테스트",
            )
        self.assertEqual(body["rt_cd"], "0")
        self.assertEqual(audit.call_count, 2)
        self.assertFalse(audit.call_args_list[0].kwargs["success"])
        self.assertTrue(audit.call_args_list[1].kwargs["success"])
        self.assertEqual(audit.call_args_list[1].kwargs["attempt"], 2)

    def test_invalid_chart_count_is_http_400(self):
        response = self.client.get("/api/kis-chart/candles?symbol=005930&count=bad")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.get_json()["ok"])

    def test_explorer_call_requires_csrf(self):
        self._login_with_csrf()
        response = self.client.post(
            "/api/kis-explorer/call", json={"id": "inquire_price", "params": {}}
        )
        self.assertEqual(response.status_code, 403)

    @patch("kis_api_explorer.can_use_kis_account", return_value=False)
    def test_explorer_account_api_requires_login(self, _access):
        csrf = self._login_with_csrf()
        response = self.client.post(
            "/api/kis-explorer/call",
            json={"id": "inquire_daily_ccld", "params": {}},
            headers={"X-CSRF-Token": csrf},
        )
        self.assertEqual(response.status_code, 401)

    @patch("broker_test_api.can_use_kis_account", return_value=True)
    def test_order_approval_requires_csrf(self, _access):
        self._login_with_csrf()
        response = self.client.post("/api/broker-test/kis/order-flow-approval", json={})
        self.assertEqual(response.status_code, 403)

    @patch("broker_test_api.run_kis_mock_order_flow_test", return_value={"order": "success"})
    @patch("broker_test_api.can_use_kis_account", return_value=True)
    def test_order_approval_is_single_use(self, _access, run_flow):
        csrf = self._login_with_csrf()
        headers = {"X-CSRF-Token": csrf}
        approval_response = self.client.post(
            "/api/broker-test/kis/order-flow-approval", json={}, headers=headers
        )
        self.assertEqual(approval_response.status_code, 200)
        approval = approval_response.get_json()["approvalToken"]

        first = self.client.post(
            "/api/broker-test/kis/order-flow-test",
            json={"approvalToken": approval},
            headers=headers,
        )
        self.assertEqual(first.status_code, 200)
        self.assertTrue(first.get_json()["ok"])
        run_flow.assert_called_once()

        replay = self.client.post(
            "/api/broker-test/kis/order-flow-test",
            json={"approvalToken": approval},
            headers=headers,
        )
        self.assertEqual(replay.status_code, 403)
        run_flow.assert_called_once()

    @patch("broker_test_api.place_kis_paper_order", return_value={"orderNo": "123", "environment": "paper"})
    @patch("broker_test_api.can_use_kis_account", return_value=True)
    def test_paper_order_approval_binds_exact_intent_and_is_single_use(self, _access, place_order):
        csrf = self._login_with_csrf()
        headers = {"X-CSRF-Token": csrf}
        intent = {"symbol": "005930", "side": "BUY", "quantity": 1, "orderType": "MARKET", "price": 0}
        approval_response = self.client.post(
            "/api/broker-test/kis/order-approval", json=intent, headers=headers,
        )
        self.assertEqual(approval_response.status_code, 200)
        token = approval_response.get_json()["approvalToken"]

        tampered = self.client.post(
            "/api/broker-test/kis/orders",
            json={**intent, "quantity": 2, "approvalToken": token}, headers=headers,
        )
        self.assertEqual(tampered.status_code, 403)
        place_order.assert_not_called()

        second_approval = self.client.post(
            "/api/broker-test/kis/order-approval", json=intent, headers=headers,
        ).get_json()["approvalToken"]
        accepted = self.client.post(
            "/api/broker-test/kis/orders",
            json={**intent, "approvalToken": second_approval}, headers=headers,
        )
        self.assertEqual(accepted.status_code, 200)
        place_order.assert_called_once_with("005930", "BUY", 1, "MARKET", 0)

        replay = self.client.post(
            "/api/broker-test/kis/orders",
            json={**intent, "approvalToken": second_approval}, headers=headers,
        )
        self.assertEqual(replay.status_code, 403)
        place_order.assert_called_once()

    @patch("broker_test.get_kis_balance", return_value={"cashBalance": "1000000", "holdings": []})
    @patch("broker_test.get_kis_quote", return_value={"price": "70000"})
    @patch("broker_test._kis_order_post", return_value={"rt_cd": "0", "msg1": "접수", "output": {"ODNO": "77"}})
    @patch("broker_test._kis_account", return_value=("12345678", "01"))
    def test_general_paper_order_uses_testbed_buy_tr_id(self, _account, order_post, _quote, _balance):
        result = broker_test.place_kis_paper_order("005930", "BUY", 1, "MARKET", 0)
        self.assertEqual(result["environment"], "paper")
        self.assertEqual(result["orderNo"], "77")
        self.assertEqual(order_post.call_args.args[1], "VTTC0012U")
        self.assertEqual(order_post.call_args.args[2]["ORD_DVSN"], "01")

if __name__ == "__main__":
    unittest.main()
