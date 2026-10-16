from unittest.mock import Mock, patch

import requests
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api.routes import krx_test

app = FastAPI()
app.include_router(krx_test.router)
client = TestClient(app)


def setup_function():
    krx_test._cache.clear()


def _ok(rows):
    response = Mock(status_code=200)
    response.json.return_value = {"OutBlock_1": rows}
    return response


ROWS = [
    {"BAS_DD": "20261015", "ISU_CD": "005930", "ISU_NM": "삼성전자", "MKT_NM": "KOSPI", "TDD_CLSPRC": "90,000", "FLUC_RT": "1.25", "ACC_TRDVOL": "12,345,678", "MKTCAP": "537,000,000,000,000"},
    {"BAS_DD": "20261015", "ISU_CD": "000660", "ISU_NM": "SK하이닉스", "MKT_NM": "KOSPI", "TDD_CLSPRC": "400,000", "FLUC_RT": "-0.50", "ACC_TRDVOL": "3,000,000", "MKTCAP": "291,000,000,000,000"},
]


def test_stock_lookup_normalizes_numbers_and_sends_key_in_header(monkeypatch):
    monkeypatch.setenv('KRX_AUTH_KEY', 'private-test-key')
    with patch.object(krx_test.requests, 'get', return_value=_ok(ROWS)) as get:
        res = client.get('/api/krx-test/stock?symbol=000660&bas_dd=20261015').json()
        assert res['ok'] and res['result']['stock']['TDD_CLSPRC'] == 400000 and res['result']['stock']['FLUC_RT'] == -0.5
        assert res['result']['market_rows'] == 2 and 'private-test-key' not in str(res)
        kwargs = get.call_args.kwargs
        assert kwargs['headers'] == {'AUTH_KEY': 'private-test-key'} and kwargs['params'] == {'basDd': '20261015'}
        assert 'private-test-key' not in get.call_args.args[0]
        top = client.get('/api/krx-test/market?bas_dd=20261015&limit=1&sort=ACC_TRDVOL').json()
        assert top['result']['stocks'][0]['ISU_CD'] == '005930' and get.call_count == 1  # 같은 시장·날짜는 캐시


def test_default_base_date_skips_weekend():
    assert len(krx_test.default_base_date()) == 8
    from datetime import datetime
    assert datetime.strptime(krx_test.default_base_date(), '%Y%m%d').weekday() < 5


def test_errors_are_safe(monkeypatch):
    monkeypatch.delenv('KRX_AUTH_KEY', raising=False)
    monkeypatch.delenv('KRX_API_KEY', raising=False)
    assert client.get('/api/krx-test/index').status_code == 503
    monkeypatch.setenv('KRX_API_KEY', 'private-test-key')
    with patch.object(krx_test.requests, 'get', return_value=Mock(status_code=403)):
        res = client.get('/api/krx-test/index?bas_dd=20261015')
        assert res.status_code == 503 and '이용 신청' in res.json()['message']
    with patch.object(krx_test.requests, 'get', return_value=_ok([])):
        assert client.get('/api/krx-test/index?service=KOSDAQ&bas_dd=20261012').status_code == 404
    with patch.object(krx_test.requests, 'get', return_value=_ok(ROWS)):
        assert client.get('/api/krx-test/stock?symbol=999999&bas_dd=20261015').status_code == 404
    with patch.object(krx_test.requests, 'get', side_effect=requests.Timeout('AUTH_KEY=private-test-key')):
        res = client.get('/api/krx-test/base-info?symbol=005930&bas_dd=20261014')
        assert res.status_code == 503 and 'private-test-key' not in res.text
    assert client.get('/api/krx-test/stock?symbol=5930').status_code == 422
    assert client.get('/api/krx-test/market?market=NYSE').status_code == 422
    assert client.get('/api/krx-test/index?bas_dd=2026-10-15').status_code == 422
