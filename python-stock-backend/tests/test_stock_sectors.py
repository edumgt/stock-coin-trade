from unittest.mock import Mock

import pytest
import requests
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import market
from app.services import stock_sectors as sectors


@pytest.fixture(autouse=True)
def clean_sector_cache():
    sectors._cache.clear()
    sectors._catalog.update(at=0, names={}, checked="")
    yield
    sectors._cache.clear()
    sectors._catalog.update(at=0, names={}, checked="")


def response(body):
    result = Mock()
    result.json.return_value = body
    return result


def test_industry_catalog_and_arbitrary_holdings_share_provider_taxonomy(monkeypatch):
    calls = []
    def get(url, **kwargs):
        calls.append((url, kwargs))
        if url == sectors.INDUSTRIES_URL:
            assert kwargs['params']['pageSize'] == 100
            return response({'totalCount': 3, 'groups': [{'no':278,'name':'반도체와반도체장비'}, {'no':266,'name':'화장품'}, {'no':263,'name':'게임엔터테인먼트'}]})
        code = url.split('/')[-2]
        return response({'itemCode':code,'stockEndType':'etf' if code=='069500' else 'stock',
                         'industryCode':{'005930':'278','161890':'266','263750':'263','069500':'25'}[code]})
    monkeypatch.setattr(sectors.requests, 'get', get)
    result = sectors.get_stock_sectors(['A005930', '161890.KS', '263750', '069500'])
    assert {k:v['sector'] for k,v in result.items()} == {'005930':'반도체와반도체장비','161890':'화장품','263750':'게임엔터테인먼트','069500':'ETF'}
    assert all(v['sectorStatus']=='verified' and v['sectorAsOf'] for v in result.values())
    sectors.get_stock_sectors(['005930','161890'])
    assert len(calls)==5


def test_provider_failure_is_unknown_and_recovers_after_retry_ttl(monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(sectors.time, 'time', lambda:clock[0])
    sectors._catalog.update(at=1000,names={'266':'화장품'})
    monkeypatch.setattr(sectors.requests, 'get', Mock(side_effect=requests.Timeout()))
    unknown = sectors.get_stock_sectors(['161890'])['161890']
    assert unknown['sector']=='분류 미확인' and unknown['sectorSource'] is None
    monkeypatch.setattr(sectors.requests, 'get', Mock(return_value=response({'itemCode':'161890','stockEndType':'stock','industryCode':'266'})))
    assert sectors.get_stock_sectors(['161890'])['161890']['sectorStatus']=='unavailable'
    clock[0] += sectors.RETRY_TTL + 1
    assert sectors.get_stock_sectors(['161890'])['161890']['sector']=='화장품'


def test_truncated_catalog_and_wrong_symbol_are_not_classified(monkeypatch):
    monkeypatch.setattr(sectors.requests,'get',Mock(return_value=response({'totalCount':79,'groups':[{'no':266,'name':'화장품'}]})))
    assert sectors.get_stock_sectors(['161890'])['161890']['sectorStatus']=='unavailable'
    sectors._catalog.update(at=sectors.time.time(),names={'266':'화장품'})
    monkeypatch.setattr(sectors.requests,'get',Mock(return_value=response({'itemCode':'005930','stockEndType':'stock','industryCode':'266'})))
    assert sectors.get_stock_sectors(['161890'])['161890']['sectorStatus']=='unavailable'


def test_sector_endpoint_validates_codes_and_does_not_use_top_n_list(monkeypatch):
    monkeypatch.setattr(sectors,'get_stock_sectors',lambda codes:{c:{'sector':'화장품'} for c in codes})
    app=FastAPI();app.include_router(market.router)
    from app.core.errors import install_exception_handlers
    install_exception_handlers(app)
    with TestClient(app) as client:
        result=client.get('/api/stocks/sectors?symbols=161890').json()
        assert result['sectors']['161890']['sector']=='화장품'
        assert client.get('/api/stocks/sectors?symbols=bad').status_code==400
        assert client.get('/api/stocks/sectors?symbols='+','.join(['161890']*101)).status_code==400


def test_personal_positions_replace_legacy_sector_without_changing_valuation(monkeypatch):
    from types import SimpleNamespace
    from app.services import stock_trading
    position = SimpleNamespace(symbol='161890',quantity=3,avg_price=100)
    db=Mock();db.scalars.return_value.all.return_value=[position]
    monkeypatch.setattr(stock_trading,'current_price',lambda code:120)
    monkeypatch.setattr(stock_trading,'get_stock_info',lambda code:{'name':'한국콜마','sector':'기타'})
    monkeypatch.setattr(stock_trading,'get_stock_sectors',lambda codes:{'161890':{'sector':'화장품','sectorSource':'네이버 금융 업종','sectorStatus':'verified','sectorAsOf':'2026-10-22T00:00:00Z'}})
    result=stock_trading.get_positions(db,1)[0]
    assert result['sector']=='화장품' and result['evalAmount']==360 and result['pnl']==60
