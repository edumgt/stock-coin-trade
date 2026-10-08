"""Binance·Korbit 공개 시세 연결 테스트."""

from __future__ import annotations

import requests
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.services.brokers.common import BrokerApiError
from app.services.crypto_exchanges import (
    get_exchange_candles,
    get_binance_orderbook,
    get_binance_symbols,
    get_binance_ticker,
    get_korbit_orderbook,
    get_korbit_ticker,
)

router = APIRouter(prefix="/api/crypto-exchange-test", tags=["crypto-exchange-test"])


def _run(build):
    try:
        return {"ok": True, "result": build()}
    except BrokerApiError as exc:
        return {"ok": False, "message": str(exc)}
    except requests.RequestException:
        return JSONResponse({"ok": False, "message": "거래소 서버 연결에 실패했습니다. 잠시 후 다시 시도하세요."}, status_code=503)


def _binance_symbol(symbol: str) -> str:
    symbol = symbol.strip().upper()
    if not symbol.isalnum() or not 6 <= len(symbol) <= 20:
        raise BrokerApiError("Binance 심볼은 BTCUSDT처럼 6~20자리 영문·숫자여야 합니다.")
    return symbol


def _korbit_symbol(symbol: str) -> str:
    symbol = symbol.strip().lower()
    if not symbol.replace("_", "").isalnum() or symbol.count("_") != 1:
        raise BrokerApiError("Korbit 거래쌍은 btc_krw처럼 코인_krw 형식이어야 합니다.")
    return symbol


@router.get("/binance/ticker")
def binance_ticker(symbol: str = Query("BTCUSDT")):
    return _run(lambda: get_binance_ticker(_binance_symbol(symbol)))


@router.get("/binance/symbols")
def binance_symbols(q: str = Query(""), quote: str = Query(""), limit: str = Query("50")):
    def build():
        query = q.strip().upper()
        quote_asset = quote.strip().upper()
        if query and (not query.isalnum() or len(query) > 20):
            raise BrokerApiError("검색어는 BTC 또는 BTCUSDT처럼 20자리 이하 영문·숫자로 입력하세요.")
        if quote_asset and (not quote_asset.isalnum() or not 2 <= len(quote_asset) <= 10):
            raise BrokerApiError("기준통화는 USDT처럼 2~10자리 영문·숫자로 입력하세요.")
        try:
            limit_value = int(limit)
        except ValueError as exc:
            raise BrokerApiError("심볼 조회 개수는 숫자여야 합니다.") from exc
        if not 1 <= limit_value <= 100:
            raise BrokerApiError("심볼 조회 개수는 1~100 사이여야 합니다.")
        return get_binance_symbols(query, quote_asset, limit_value)

    return _run(build)


@router.get("/binance/orderbook")
def binance_orderbook(symbol: str = Query("BTCUSDT")):
    return _run(lambda: get_binance_orderbook(_binance_symbol(symbol)))


@router.get("/korbit/ticker")
def korbit_ticker(symbol: str = Query("btc_krw")):
    return _run(lambda: get_korbit_ticker(_korbit_symbol(symbol)))


@router.get("/korbit/orderbook")
def korbit_orderbook(symbol: str = Query("btc_krw")):
    return _run(lambda: get_korbit_orderbook(_korbit_symbol(symbol)))


@router.get("/{exchange}/candles")
def exchange_candles(exchange: str, symbol: str = Query(...), interval: str = Query("1h"), limit: int = Query(200, ge=1, le=200)):
    def build():
        if exchange not in {"binance", "korbit"}:
            raise BrokerApiError("지원하지 않는 거래소입니다.")
        normalized = _binance_symbol(symbol) if exchange == "binance" else _korbit_symbol(symbol)
        return get_exchange_candles(exchange, normalized, interval, limit)
    return _run(build)
