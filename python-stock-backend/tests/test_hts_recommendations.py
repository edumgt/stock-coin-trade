"""/api/hts/recommendations — fd quant-dashboard 강력매수 후보 중계."""
from unittest.mock import Mock, patch

import requests
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import hts

app = FastAPI()
app.include_router(hts.router)
client = TestClient(app)


def setup_function():
    hts._cache.clear()


def _upstream():
    return {
        "stocks": [
            {"symbol": "207940.KS", "code": "207940", "name": "삼성바이오로직스", "market": "KOSPI", "sector": "제약", "market_cap_eok": 655942, "kis_order_allowed": True},
            {"symbol": "005930.KS", "code": "005930", "name": "삼성전자", "market": "KOSPI", "sector": "반도체"},
            {"symbol": "393210.KQ", "code": "393210", "name": "토마토시스템", "market": "KOSDAQ", "sector": "SW"},
        ],
        "indicators": {
            "207940.KS": {"rsi": [50.0, 61.2], "as_of": "2026-10-21", "signal": {"action": "강력 매수", "score": 3, "reasons": ["골든크로스", "RSI 중립"]}},
            "005930.KS": {"rsi": [40.0], "as_of": "2026-10-21", "signal": {"action": "관망", "score": 0, "reasons": []}},
            "393210.KQ": {"rsi": [70.1], "as_of": "2026-10-21", "signal": {"action": "강력 매수", "score": 4, "reasons": ["볼린저 하단"]}},
        },
        "updated_at": "2026-10-22T02:19:42+00:00",
        "signal_policy": {"method": "daily_technical_rules", "strong_buy_threshold": 3},
    }


def test_filters_strong_buy_and_shapes_symbols():
    response = Mock(status_code=200)
    response.json.return_value = _upstream()
    response.raise_for_status.return_value = None
    with patch.object(hts.requests, "get", return_value=response) as get:
        body = client.get("/api/hts/recommendations?limit=10").json()
        assert body["ok"] is True and body["strongBuyThreshold"] == 3
        assert [s["symbol"] for s in body["stocks"]] == ["207940", "393210"]      # 관망(삼성전자)은 제외, 상류 순서 유지
        first = body["stocks"][0]
        assert first["yahooSymbol"] == "207940.KS" and first["market"] == "KOSPI" and first["rsi"] == 61.2 and first["score"] == 3
        assert body["stocks"][1]["yahooSymbol"] == "393210.KQ"
        assert "fd.edumgt.co.kr/api" not in str(body)                            # 상류 URL 미노출
        # 60초 캐시: 같은 limit 재요청은 상류를 다시 부르지 않는다
        assert client.get("/api/hts/recommendations?limit=10").json() == body
        assert get.call_count == 1
        assert get.call_args.kwargs["params"]["limit"] == 20


def test_limit_caps_results():
    response = Mock(status_code=200)
    response.json.return_value = _upstream()
    response.raise_for_status.return_value = None
    with patch.object(hts.requests, "get", return_value=response):
        body = client.get("/api/hts/recommendations?limit=1").json()
        assert [s["symbol"] for s in body["stocks"]] == ["207940"]


def test_upstream_down_returns_503_json():
    with patch.object(hts.requests, "get", side_effect=requests.ConnectionError("down")):
        res = client.get("/api/hts/recommendations")
        assert res.status_code == 503
        assert res.json()["ok"] is False and "연결" in res.json()["message"]
        assert not hts._cache                                                     # 실패는 캐시하지 않는다


def test_bad_upstream_shape_returns_502():
    response = Mock(status_code=200)
    response.json.return_value = {"unexpected": True}
    response.raise_for_status.return_value = None
    with patch.object(hts.requests, "get", return_value=response):
        res = client.get("/api/hts/recommendations")
        assert res.status_code == 502 and res.json()["ok"] is False
