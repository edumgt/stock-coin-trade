import unittest
from unittest.mock import Mock, patch

import crypto_exchange_test as market


class BinanceSymbolSearchTest(unittest.TestCase):
    def setUp(self):
        market._binance_symbols_cache.update({"expires_at": 0.0, "symbols": []})

    @staticmethod
    def response():
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

    @patch("crypto_exchange_test.requests.get")
    def test_searches_trading_spot_symbols_by_asset_and_quote(self, get):
        get.return_value = self.response()
        result = market.get_binance_symbols("BTC", "USDT", 50)
        self.assertEqual([{"symbol": "BTCUSDT", "baseAsset": "BTC", "quoteAsset": "USDT", "status": "TRADING"}], result["symbols"])
        self.assertEqual(1, result["totalMatches"])

    @patch("crypto_exchange_test.requests.get")
    def test_excludes_non_trading_symbols_and_honors_limit(self, get):
        get.return_value = self.response()
        result = market.get_binance_symbols("", "USDT", 1)
        self.assertEqual(2, result["totalMatches"])
        self.assertEqual(1, len(result["symbols"]))
        self.assertNotEqual("OLDUSDT", result["symbols"][0]["symbol"])

    @patch("crypto_exchange_test.requests.get")
    def test_reuses_exchange_info_cache(self, get):
        get.return_value = self.response()
        market.get_binance_symbols("BTC", "", 50)
        market.get_binance_symbols("ETH", "", 50)
        self.assertEqual(1, get.call_count)


if __name__ == "__main__":
    unittest.main()
