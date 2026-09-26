"""KIS 종목 차트 웹앱 백엔드 (/api/kis-chart/*).

.env의 모의투자 App Key·Secret 으로 KIS Testbed 의 시세 API 를 호출해
차트용 캔들 데이터를 만든다. 계좌 정보는 필요 없고, 읽기 전용이며 로그인도 요구하지 않는다.

- /candles  : 국내주식기간별시세 (inquire-daily-itemchartprice, FHKST03010100)
              일/주/월/년봉. 한 번에 최대 100건이라 날짜 구간을 뒤로 옮기며 여러 번 호출한다.
- /minutes  : 주식당일분봉조회 (inquire-time-itemchartprice, FHKST03010200)
              당일 1분봉. 한 번에 30건이라 시각을 뒤로 옮기며 여러 번 호출한다.
응답 캔들은 오래된 순(오름차순)으로 정렬해 lightweight-charts 에 바로 넣을 수 있게 한다.
"""
from __future__ import annotations

import threading
import time
from collections import OrderedDict
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import requests
from flask import Blueprint, jsonify, request

from broker_test import BrokerApiError, kis_request

kis_chart_bp = Blueprint("kis_chart", __name__, url_prefix="/api/kis-chart")

_PERIOD_WINDOW_DAYS = {"D": 150, "W": 730, "M": 3300, "Y": 40000}  # 호출당 100건을 채울 만한 달력 일수
_MAX_CANDLES = 300
_MAX_MINUTES = 240
_CACHE_TTL_SECONDS = 30
_CACHE_MAX_ENTRIES = 256
_SEOUL = ZoneInfo("Asia/Seoul")

_cache_lock = threading.Lock()
_cache: OrderedDict[str, tuple[float, dict[str, Any]]] = OrderedDict()


def _num(value: Any) -> float | None:
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    n = _num(value)
    return int(n) if n is not None else None


def _symbol() -> str:
    symbol = request.args.get("symbol", "005930").strip()
    if len(symbol) != 6 or not symbol.isdigit():
        raise BrokerApiError("종목코드는 6자리 KRX 숫자 코드여야 합니다.", 400)
    return symbol


def _cached(key: str, build):
    now = time.time()
    with _cache_lock:
        hit = _cache.get(key)
        if hit and hit[0] > now:
            _cache.move_to_end(key)
            return hit[1]
        _cache.pop(key, None)
    data = build()
    with _cache_lock:
        _cache[key] = (time.time() + _CACHE_TTL_SECONDS, data)
        _cache.move_to_end(key)
        while len(_cache) > _CACHE_MAX_ENTRIES:
            _cache.popitem(last=False)
    return data


def _kis_get(path: str, tr_id: str, params: dict[str, str], label: str) -> dict[str, Any]:
    _, body = kis_request(
        "GET", path, tr_id, params=params, label=label,
        extra_headers={"custtype": "P"},
    )
    return body


def _summary(output1: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": output1.get("hts_kor_isnm"),
        "price": _num(output1.get("stck_prpr")),
        "change": _num(output1.get("prdy_vrss")),
        "changeRate": _num(output1.get("prdy_ctrt")),
        "changeSign": output1.get("prdy_vrss_sign"),
        "prevClose": _num(output1.get("stck_prdy_clpr")),
        "open": _num(output1.get("stck_oprc")),
        "high": _num(output1.get("stck_hgpr")),
        "low": _num(output1.get("stck_lwpr")),
        "volume": _int(output1.get("acml_vol")),
        "amount": _int(output1.get("acml_tr_pbmn")),
        "upperLimit": _num(output1.get("stck_mxpr")),
        "lowerLimit": _num(output1.get("stck_llam")),
        "per": _num(output1.get("per")),
        "eps": _num(output1.get("eps")),
        "pbr": _num(output1.get("pbr")),
        "marketCap": _int(output1.get("hts_avls")),
        "listedShares": _int(output1.get("lstn_stcn")),
    }


def _period_candles(symbol: str, period: str, count: int, end: date) -> dict[str, Any]:
    window = _PERIOD_WINDOW_DAYS[period]
    candles: dict[str, dict[str, Any]] = {}
    summary: dict[str, Any] | None = None
    cursor_end = end
    for _ in range(4):  # 최대 4회 호출 (일봉 기준 약 400 영업일)
        start = cursor_end - timedelta(days=window)
        body = _kis_get(
            "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice", "FHKST03010100",
            {
                "FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": symbol,
                "FID_INPUT_DATE_1": start.strftime("%Y%m%d"), "FID_INPUT_DATE_2": cursor_end.strftime("%Y%m%d"),
                "FID_PERIOD_DIV_CODE": period, "FID_ORG_ADJ_PRC": "0",
            },
            "기간별 시세 조회",
        )
        if summary is None:
            summary = _summary(body.get("output1") or {})
        rows = [r for r in (body.get("output2") or []) if r.get("stck_bsop_date")]
        for r in rows:
            d = r["stck_bsop_date"]
            candles[d] = {
                "time": f"{d[:4]}-{d[4:6]}-{d[6:]}",
                "open": _num(r.get("stck_oprc")), "high": _num(r.get("stck_hgpr")),
                "low": _num(r.get("stck_lwpr")), "close": _num(r.get("stck_clpr")),
                "volume": _int(r.get("acml_vol")), "amount": _int(r.get("acml_tr_pbmn")),
            }
        if len(candles) >= count or not rows:
            break
        oldest = min(r["stck_bsop_date"] for r in rows)
        cursor_end = datetime.strptime(oldest, "%Y%m%d").date() - timedelta(days=1)
    ordered = [c for _, c in sorted(candles.items())][-count:]
    return {"broker": "한국투자증권 Testbed", "symbol": symbol, "period": period, "count": len(ordered), "summary": summary, "candles": ordered}


def _minute_candles(symbol: str, count: int, end_time: str) -> dict[str, Any]:
    candles: dict[str, dict[str, Any]] = {}
    summary: dict[str, Any] | None = None
    cursor = end_time
    for _ in range(8):  # 30건 × 8 = 240분
        body = _kis_get(
            "/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice", "FHKST03010200",
            {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": symbol, "FID_INPUT_HOUR_1": cursor, "FID_PW_DATA_INCU_YN": "Y", "FID_ETC_CLS_CODE": ""},
            "당일 분봉 조회",
        )
        if summary is None:
            summary = _summary(body.get("output1") or {})
        rows = [r for r in (body.get("output2") or []) if r.get("stck_cntg_hour")]
        new = 0
        for r in rows:
            d, t = r.get("stck_bsop_date") or "", r["stck_cntg_hour"]
            key = d + t
            if key in candles:
                continue
            new += 1
            candles[key] = {
                "time": f"{d[:4]}-{d[4:6]}-{d[6:]} {t[:2]}:{t[2:4]}",
                "timestamp": int(datetime.strptime(d + t[:4], "%Y%m%d%H%M").replace(tzinfo=_SEOUL).timestamp()) if len(d) == 8 else None,
                "open": _num(r.get("stck_oprc")), "high": _num(r.get("stck_hgpr")),
                "low": _num(r.get("stck_lwpr")), "close": _num(r.get("stck_prpr")),
                "volume": _int(r.get("cntg_vol")), "amount": _int(r.get("acml_tr_pbmn")),
            }
        if len(candles) >= count or not rows or new == 0:
            break
        earliest = min(r["stck_cntg_hour"] for r in rows)
        prev = datetime.strptime(earliest[:4], "%H%M") - timedelta(minutes=1)
        if prev.strftime("%H%M") < "0900":
            break
        cursor = prev.strftime("%H%M") + "00"
    ordered = [c for _, c in sorted(candles.items())][-count:]
    return {"broker": "한국투자증권 Testbed", "symbol": symbol, "period": "1m", "count": len(ordered), "summary": summary, "candles": ordered}


def _respond(build):
    try:
        return jsonify({"ok": True, **build()})
    except BrokerApiError as exc:
        return jsonify({"ok": False, "broker": "한국투자증권 Testbed", "message": str(exc)}), exc.status_code
    except (TypeError, ValueError):
        return jsonify({"ok": False, "broker": "한국투자증권 Testbed", "message": "조회 파라미터 형식이 올바르지 않습니다."}), 400
    except requests.RequestException:
        return jsonify({"ok": False, "broker": "한국투자증권 Testbed", "message": "한국투자증권 서버 연결에 실패했습니다. 잠시 후 다시 시도하세요."}), 503


@kis_chart_bp.get("/candles")
def candles():
    def build():
        symbol = _symbol()
        period = request.args.get("period", "D").upper()
        if period not in _PERIOD_WINDOW_DAYS:
            raise BrokerApiError("period 는 D(일), W(주), M(월), Y(년) 중 하나여야 합니다.", 400)
        count = max(20, min(_MAX_CANDLES, int(request.args.get("count", 120) or 120)))
        end_raw = request.args.get("end", "").strip()
        end = datetime.strptime(end_raw, "%Y%m%d").date() if end_raw else datetime.now(_SEOUL).date()
        return _cached(f"{symbol}:{period}:{count}:{end}", lambda: _period_candles(symbol, period, count, end))
    return _respond(build)


@kis_chart_bp.get("/minutes")
def minutes():
    def build():
        symbol = _symbol()
        count = max(30, min(_MAX_MINUTES, int(request.args.get("count", 120) or 120)))
        end_time = request.args.get("time", "").strip() or "153000"
        if len(end_time) != 6 or not end_time.isdigit():
            raise BrokerApiError("time 은 HHMMSS 형식이어야 합니다.", 400)
        if not ("090000" <= end_time <= "153000"):
            raise BrokerApiError("time 은 정규장 시간(090000~153000) 범위여야 합니다.", 400)
        return _cached(f"{symbol}:1m:{count}:{end_time}", lambda: _minute_candles(symbol, count, end_time))
    return _respond(build)
