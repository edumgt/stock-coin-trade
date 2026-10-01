from unittest.mock import Mock, patch

import pytest

from app.services import crypto_exchanges as market


@pytest.fixture(autouse=True)
def _reset_cache():
    market._binance_symbols_cache.update({"expires_at": 0.0, "symbols": []})


def _response():
    response = Mock()
    response.ok = True
    response.status_code = 200
    response.json.return_value = {
        "symbols": [
            {"symbol": "BTCUSDT", "baseAsset": "BTC", "quoteAsset": "USDT", "status": "TRADING"},
            {"symbol": "BTCUSDC", "baseAsset": "BTC", "quoteAsset": "USDC", "status": "TRADING"},
            {"symbol": "ETHUSDT", "baseAsset": "ETH", "quoteAsset": "USDT", "status": "TRADING"},
            {"symbol": "OLDUSDT", "baseAsset": "OLD", "quoteAsset": "USDT", "status": "BREAK"},
        ]
    }
    return response


@patch("app.services.crypto_exchanges.requests.get")
def test_searches_trading_spot_symbols_by_asset_and_quote(get):
    get.return_value = _response()
    result = market.get_binance_symbols("BTC", "USDT", 50)
    assert result["symbols"] == [{"symbol": "BTCUSDT", "baseAsset": "BTC", "quoteAsset": "USDT", "status": "TRADING"}]
    assert result["totalMatches"] == 1


@patch("app.services.crypto_exchanges.requests.get")
def test_excludes_non_trading_symbols_and_honors_limit(get):
    get.return_value = _response()
    result = market.get_binance_symbols("", "USDT", 1)
    assert result["totalMatches"] == 2
    assert len(result["symbols"]) == 1
    assert result["symbols"][0]["symbol"] != "OLDUSDT"


@patch("app.services.crypto_exchanges.requests.get")
def test_reuses_exchange_info_cache(get):
    get.return_value = _response()
    market.get_binance_symbols("BTC", "", 50)
    market.get_binance_symbols("ETH", "", 50)
    assert get.call_count == 1


@patch("app.api.routes.crypto_exchange_test.get_binance_ticker", return_value={"exchange": "Binance Spot", "symbol": "BTCUSDT"})
def test_ticker_route_wraps_result(ticker, client):
    response = client.get("/api/crypto-exchange-test/binance/ticker?symbol=btcusdt")
    assert response.status_code == 200
    assert response.json() == {"ok": True, "result": {"exchange": "Binance Spot", "symbol": "BTCUSDT"}}
    ticker.assert_called_once_with("BTCUSDT")


def test_invalid_binance_symbol_is_reported_in_body(client):
    response = client.get("/api/crypto-exchange-test/binance/ticker?symbol=x")
    assert response.status_code == 200
    assert response.json()["ok"] is False
