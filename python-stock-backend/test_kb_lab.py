import unittest
from unittest.mock import Mock, patch

from flask import Flask

import broker_test
from broker_test_api import broker_test_bp


class KbLabTest(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.config.update(SECRET_KEY="test-secret", TESTING=True)
        app.register_blueprint(broker_test_bp)
        self.client = app.test_client()

    def login(self):
        with self.client.session_transaction() as sess:
            sess["member_id"] = 7

    def test_kb_status_requires_login(self):
        response = self.client.get("/api/broker-test/kb/status")
        self.assertEqual(response.status_code, 401)

    @patch("broker_test_api.get_kb_configuration_status")
    def test_kb_status_returns_no_secret_values(self, status):
        status.return_value = {
            "configured": True, "source": "environment", "environment": {"complete": True},
            "endpoint": broker_test.KB_API_BASE_URL, "mode": "production", "readOnly": True,
        }
        self.login()
        response = self.client.get("/api/broker-test/kb/status")
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertTrue(body["status"]["configured"])
        self.assertNotIn("appSecret", str(body))

    @patch("broker_test._audit_kb_call")
    @patch("broker_test._kb_data_header", return_value={})
    @patch("broker_test._credentials", return_value=("key", "secret"))
    @patch("broker_test._kb_token_response", return_value={"access_token": "token"})
    @patch("broker_test.requests.post")
    def test_business_error_on_http_200_is_rejected_and_audited(self, request_call, _token, _credentials, _header, audit):
        response = Mock(status_code=200, ok=True)
        response.json.return_value = {"dataHeader": {"processCode": "E123", "processMessage": "권한 없음"}, "dataBody": {}}
        request_call.return_value = response
        with self.assertRaises(broker_test.BrokerApiError):
            broker_test._kb_investment_info("/api/v1/ivu10140", {"shrt_cd": "005930"})
        self.assertFalse(audit.call_args.kwargs["success"])

    @patch("broker_test._audit_kb_call")
    @patch("broker_test._kb_data_header", return_value={})
    @patch("broker_test._credentials", return_value=("key", "secret"))
    @patch("broker_test._kb_token_response", return_value={"access_token": "token"})
    @patch("broker_test.requests.post")
    def test_process_code_0024_is_normal_completion(self, request_call, _token, _credentials, _header, audit):
        response = Mock(status_code=200, ok=True)
        response.json.return_value = {
            "dataHeader": {"processCode": "0024", "processMessage": "정상적으로 조회가 완료되었습니다."},
            "dataBody": {"out2": []},
        }
        request_call.return_value = response
        result = broker_test._kb_investment_info("/api/v1/ivs11560", {})
        self.assertEqual(result, {"out2": []})
        self.assertTrue(audit.call_args.kwargs["success"])

    @patch("broker_test._kb_investment_info")
    def test_chart_normalizes_official_ivs11560_fields(self, call):
        broker_test._kb_chart_cache.clear()
        call.return_value = {"out2": [
            {"dt": "20260918", "opn_prc_p2": " 261000", "hgh_prc_p2": "262000",
             "lw_prc_p2": "257500", "cls_prc_p2": "260000", "vlm": "17489615", "dl_tw_amt": "455429100625"},
            {"dt": "20260917", "opn_prc_p2": " 250000", "hgh_prc_p2": "255000",
             "lw_prc_p2": "249000", "cls_prc_p2": "252500", "vlm": "100", "dl_tw_amt": "200"},
        ]}
        result = broker_test.get_kb_stock_chart("005930", "0", "D", 60)
        self.assertEqual(result["source"], "IVS11560")
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["candles"][0]["time"], "2026-09-17")
        self.assertEqual(result["candles"][1]["close"], 260000)
        request_body = call.call_args.args[1]
        self.assertEqual(request_body["mkt_clsf"], "0")
        self.assertEqual(request_body["inq_clsf"], "2")


if __name__ == "__main__":
    unittest.main()
