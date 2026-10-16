import io
import zipfile
from unittest.mock import Mock, patch

import requests
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api.routes import dart_test

app = FastAPI()
app.include_router(dart_test.router)
client = TestClient(app)


def _corp_zip():
    xml = ('<?xml version="1.0" encoding="UTF-8"?><result><list><corp_code>00126380</corp_code><corp_name>삼성전자</corp_name>'
           '<stock_code>005930</stock_code><modify_date>20260101</modify_date></list><list><corp_code>00999999</corp_code>'
           '<corp_name>비상장</corp_name><stock_code> </stock_code></list></result>')
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("CORPCODE.xml", xml)
    return buffer.getvalue()


def setup_function():
    dart_test._cache.clear()
    dart_test._corp_cache.update(ts=0.0, map={}, names={})


def _responses(json_body):
    """corpCode.xml 요청에는 ZIP, 나머지에는 json_body 를 돌려주는 side_effect(고유번호 캐시 여부와 무관)."""
    def side_effect(url, **kwargs):
        if url.endswith("corpCode.xml"):
            return Mock(status_code=200, content=_corp_zip())
        api = Mock(status_code=200)
        api.json.return_value = json_body
        return api
    return side_effect


def test_company_resolves_preferred_to_common_and_caches(monkeypatch):
    monkeypatch.setenv('DART_API_KEY', 'private-test-key')
    body = {"status": "000", "message": "정상", "corp_name": "삼성전자", "stock_code": "005930", "corp_cls": "Y", "ceo_nm": "홍길동"}
    with patch.object(dart_test.requests, 'get', side_effect=_responses(body)) as get:
        res = client.get('/api/dart-test/company?stock_code=005935').json()
        assert res['ok'] and res['result']['resolved_stock_code'] == '005930' and res['result']['is_preferred'] is True
        assert res['result']['company']['corp_cls_name'] == '유가증권(KOSPI)'
        assert 'private-test-key' not in str(res)
        assert client.get('/api/dart-test/company?stock_code=005935').json() == res
        assert get.call_count == 2  # corpCode.xml + company.json, 두 번째 호출은 캐시


def test_financials_parse_amounts_and_summary(monkeypatch):
    monkeypatch.setenv('DART_API_KEY', 'private-test-key')
    rows = [
        {"fs_div": "CFS", "sj_div": "BS", "sj_nm": "재무상태표", "account_nm": "자산총계", "thstrm_nm": "제 57 기", "thstrm_amount": "1,000", "frmtrm_amount": "900", "currency": "KRW"},
        {"fs_div": "CFS", "sj_div": "BS", "account_nm": "부채총계", "thstrm_amount": "400"},
        {"fs_div": "CFS", "sj_div": "BS", "account_nm": "자본총계", "thstrm_amount": "600"},
        {"fs_div": "CFS", "sj_div": "SCE", "account_nm": "자본총계", "thstrm_amount": "999"},
        {"fs_div": "CFS", "sj_div": "IS", "account_nm": "매출액", "thstrm_amount": "5,000"},
        {"fs_div": "CFS", "sj_div": "IS", "account_nm": "영업이익", "thstrm_amount": "(300)"},
        {"fs_div": "CFS", "sj_div": "IS", "account_nm": "당기순이익", "thstrm_amount": "-"},
    ]
    with patch.object(dart_test.requests, 'get', side_effect=_responses({"status": "000", "list": rows})):
        res = client.get('/api/dart-test/financials?stock_code=005930&bsns_year=2025').json()
    summary = res['result']['summary']
    assert summary == {"assets": 1000, "liabilities": 400, "equity": 600, "revenue": 5000, "operating_income": -300, "net_income": None}
    assert res['result']['status'] == 'partial' and res['result']['fs_div'] == '연결' and res['result']['report_name'] == '사업보고서'


def test_dart_status_codes_and_safe_errors(monkeypatch):
    monkeypatch.delenv('DART_API_KEY', raising=False)
    assert client.get('/api/dart-test/company').status_code == 503
    monkeypatch.setenv('DART_API_KEY', 'private-test-key')
    with patch.object(dart_test.requests, 'get', side_effect=_responses({"status": "013", "message": "조회된 데이타가 없습니다."})):
        res = client.get('/api/dart-test/disclosures?stock_code=005930')
        assert res.status_code == 404 and '자료가 없습니다' in res.json()['message']
    with patch.object(dart_test.requests, 'get', side_effect=_responses({"status": "020", "message": "요청 제한"})):
        assert client.get('/api/dart-test/disclosures?stock_code=005930&days=7').status_code == 503
    with patch.object(dart_test.requests, 'get', side_effect=requests.Timeout('url?crtfc_key=private-test-key')):
        res = client.get('/api/dart-test/company?stock_code=005930')  # 고유번호는 캐시됨 → company.json 에서 Timeout
        assert res.status_code == 503 and 'private-test-key' not in res.text
    corp = Mock(status_code=200, content=_corp_zip())
    with patch.object(dart_test.requests, 'get', return_value=corp):
        assert client.get('/api/dart-test/company?stock_code=123456').status_code == 404
    assert client.get('/api/dart-test/company?stock_code=12345').status_code == 422
    assert client.get('/api/dart-test/financials?reprt_code=99999').status_code == 422
    assert client.get('/api/dart-test/disclosures?days=400').status_code == 422
