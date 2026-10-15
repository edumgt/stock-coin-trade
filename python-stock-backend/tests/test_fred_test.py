from unittest.mock import Mock, patch

import requests
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api.routes import fred_test

app = FastAPI()
app.include_router(fred_test.router)
client = TestClient(app)


def setup_function():
    fred_test._cache.clear()


def test_observations_normalize_missing_and_preserve_asof(monkeypatch):
    monkeypatch.setenv('FRED_API_KEY', 'private-test-key')
    response = Mock(status_code=200)
    response.json.return_value = {'observations': [{'date': '2026-10-14', 'value': '.'}, {'date': '2026-10-13', 'value': '4.2'}]}
    with patch.object(fred_test.requests, 'get', return_value=response) as get:
        body = client.get('/api/fred-test/observations?series_id=DGS10').json()
        assert body['result']['status'] == 'partial'
        assert body['result']['as_of'] == '2026-10-13'
        assert body['result']['observations'][0]['value'] is None
        assert 'private-test-key' not in str(body)
        assert client.get('/api/fred-test/observations?series_id=DGS10').json() == body
        assert get.call_count == 1


def test_safe_errors_and_validation(monkeypatch):
    monkeypatch.delenv('FRED_API_KEY', raising=False)
    assert client.get('/api/fred-test/series').status_code == 503
    monkeypatch.setenv('FRED_API_KEY', 'private-test-key')
    with patch.object(fred_test.requests, 'get', side_effect=requests.Timeout('url?api_key=private-test-key')):
        response = client.get('/api/fred-test/series')
        assert response.status_code == 503
        assert 'private-test-key' not in response.text
    assert client.get('/api/fred-test/observations?limit=201').status_code == 422
    assert client.get('/api/fred-test/series?series_id=https://example.com').status_code == 422
