import requests

from flask import Blueprint, jsonify, request

from broker_test import BrokerApiError
from crypto_exchange_test import get_binance_orderbook, get_binance_ticker, get_korbit_orderbook, get_korbit_ticker


crypto_exchange_test_bp = Blueprint("crypto_exchange_test", __name__, url_prefix="/api/crypto-exchange-test")


def _run(build):
    try:
        return jsonify({"ok": True, "result": build()})
    except BrokerApiError as exc:
        return jsonify({"ok": False, "message": str(exc)})
    except requests.RequestException:
        return jsonify({"ok": False, "message": "거래소 서버 연결에 실패했습니다. 잠시 후 다시 시도하세요."}), 503


def _binance_symbol() -> str:
    symbol = request.args.get("symbol", "BTCUSDT").strip().upper()
    if not symbol.isalnum() or not 6 <= len(symbol) <= 20:
        raise BrokerApiError("Binance 심볼은 BTCUSDT처럼 6~20자리 영문·숫자여야 합니다.")
    return symbol


def _korbit_symbol() -> str:
    symbol = request.args.get("symbol", "btc_krw").strip().lower()
    if not symbol.replace("_", "").isalnum() or symbol.count("_") != 1:
        raise BrokerApiError("Korbit 거래쌍은 btc_krw처럼 코인_krw 형식이어야 합니다.")
    return symbol


@crypto_exchange_test_bp.get("/binance/ticker")
def binance_ticker():
    return _run(lambda: get_binance_ticker(_binance_symbol()))


@crypto_exchange_test_bp.get("/binance/orderbook")
def binance_orderbook():
    return _run(lambda: get_binance_orderbook(_binance_symbol()))


@crypto_exchange_test_bp.get("/korbit/ticker")
def korbit_ticker():
    return _run(lambda: get_korbit_ticker(_korbit_symbol()))


@crypto_exchange_test_bp.get("/korbit/orderbook")
def korbit_orderbook():
    return _run(lambda: get_korbit_orderbook(_korbit_symbol()))
