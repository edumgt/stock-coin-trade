"""KIS 종목 차트 웹앱 백엔드 (/api/kis-chart/*). 읽기 전용이며 로그인을 요구하지 않는다."""

from __future__ import annotations

from datetime import datetime

import requests
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.services.brokers.common import BrokerApiError
from app.services.brokers.kis_chart import (
    MAX_CANDLES,
    MAX_MINUTES,
    PERIOD_WINDOW_DAYS,
    SEOUL,
    cached,
    minute_candles,
    period_candles,
)

router = APIRouter(prefix="/api/kis-chart", tags=["kis"])
BROKER = "한국투자증권 Testbed"


def _symbol(symbol: str) -> str:
    symbol = symbol.strip()
    if len(symbol) != 6 or not symbol.isdigit():
        raise BrokerApiError("종목코드는 6자리 KRX 숫자 코드여야 합니다.", 400)
    return symbol


def _respond(build):
    try:
        return {"ok": True, **build()}
    except BrokerApiError as exc:
        return JSONResponse({"ok": False, "broker": BROKER, "message": str(exc)}, status_code=exc.status_code)
    except (TypeError, ValueError):
        return JSONResponse({"ok": False, "broker": BROKER, "message": "조회 파라미터 형식이 올바르지 않습니다."}, status_code=400)
    except requests.RequestException:
        return JSONResponse({"ok": False, "broker": BROKER, "message": "한국투자증권 서버 연결에 실패했습니다. 잠시 후 다시 시도하세요."}, status_code=503)


@router.get("/candles")
def candles(symbol: str = Query("005930"), period: str = Query("D"), count: str = Query("120"), end: str = Query("")):
    def build():
        code = _symbol(symbol)
        period_code = period.upper()
        if period_code not in PERIOD_WINDOW_DAYS:
            raise BrokerApiError("period 는 D(일), W(주), M(월), Y(년) 중 하나여야 합니다.", 400)
        count_value = max(20, min(MAX_CANDLES, int(count or 120)))
        end_raw = end.strip()
        end_date = datetime.strptime(end_raw, "%Y%m%d").date() if end_raw else datetime.now(SEOUL).date()
        return cached(f"{code}:{period_code}:{count_value}:{end_date}", lambda: period_candles(code, period_code, count_value, end_date))

    return _respond(build)


@router.get("/minutes")
def minutes(symbol: str = Query("005930"), count: str = Query("120"), time: str = Query("")):
    def build():
        code = _symbol(symbol)
        count_value = max(30, min(MAX_MINUTES, int(count or 120)))
        end_time = time.strip() or "153000"
        if len(end_time) != 6 or not end_time.isdigit():
            raise BrokerApiError("time 은 HHMMSS 형식이어야 합니다.", 400)
        if not ("090000" <= end_time <= "153000"):
            raise BrokerApiError("time 은 정규장 시간(090000~153000) 범위여야 합니다.", 400)
        return cached(f"{code}:1m:{count_value}:{end_time}", lambda: minute_candles(code, count_value, end_time))

    return _respond(build)
