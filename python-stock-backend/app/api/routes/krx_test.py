"""KRX 정보데이터시스템 Open API(openapi.krx.co.kr) 읽기 전용 학습 엔드포인트. 업스트림 URL·인증키는 응답에 싣지 않는다.

규약(2026-10-16 확인, 비공식 클라이언트 명세 종합):
  - 요청: `https://data-dbg.krx.co.kr/svc/apis/<서비스>/<API>` GET, 인증키는 HTTP 헤더 `AUTH_KEY`, 파라미터 `basDd=YYYYMMDD`.
  - 응답: `OutBlock_1` 배열 하나. 숫자도 문자열(쉼표 포함)로 온다.
  - 데이터는 2010년 이후 ~ 조회일 전 영업일(T-1)까지이고 매일 아침 갱신된다. 서비스마다 이용 신청·승인이 따로 필요하다.
"""
import os
from datetime import datetime, timedelta, timezone
from threading import Lock
from time import monotonic

import requests
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/krx-test", tags=["krx-test"])
_BASE = "https://data-dbg.krx.co.kr/svc/apis/"
_SOURCE = "한국거래소(KRX) 정보데이터시스템 Open API"
_CACHE_SECONDS = 300
_cache = {}
_lock = Lock()
_KST = timezone(timedelta(hours=9))

MARKETS = {"KOSPI": ("sto/stk_bydd_trd", "sto/stk_isu_base_info"), "KOSDAQ": ("sto/ksq_bydd_trd", "sto/ksq_isu_base_info"),
           "KONEX": ("sto/knx_bydd_trd", "sto/knx_isu_base_info")}
INDEX_SERVICES = {"KRX": "idx/krx_dd_trd", "KOSPI": "idx/kospi_dd_trd", "KOSDAQ": "idx/kosdaq_dd_trd"}
_NUMERIC = ("TDD_CLSPRC", "CMPPREVDD_PRC", "FLUC_RT", "TDD_OPNPRC", "TDD_HGPRC", "TDD_LWPRC", "ACC_TRDVOL", "ACC_TRDVAL",
            "MKTCAP", "LIST_SHRS", "CLSPRC_IDX", "CMPPREVDD_IDX", "OPNPRC_IDX", "HGPRC_IDX", "LWPRC_IDX", "PARVAL")


def _api_key() -> str:
    for name in ("KRX_AUTH_KEY", "KRX_API_KEY"):
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def _error(message: str, status_code: int = 502):
    return JSONResponse({"ok": False, "message": message}, status_code=status_code)


def _number(value):
    text = str(value if value is not None else "").replace(",", "").strip()
    if text in ("", "-"):
        return None
    try:
        return int(text) if text.lstrip("-").isdigit() else float(text)
    except ValueError:
        return None


def _normalize(row: dict) -> dict:
    return {key: (_number(value) if key in _NUMERIC else value) for key, value in row.items()}


def default_base_date() -> str:
    """KRX 는 T-1 까지만 준다. 주말이면 금요일로 당긴다(공휴일은 호출자가 날짜를 바꿔 재시도)."""
    day = datetime.now(_KST).date() - timedelta(days=1)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day.strftime("%Y%m%d")


def _fetch(service: str, bas_dd: str):
    key = _api_key()
    if not key:
        return _error("서버에 KRX_AUTH_KEY가 설정되지 않았습니다.", 503)
    cache_key = (service, bas_dd)
    with _lock:
        cached = _cache.get(cache_key)
        if cached and monotonic() - cached[0] < _CACHE_SECONDS:
            return cached[1]
    try:
        response = requests.get(_BASE + service, params={"basDd": bas_dd}, headers={"AUTH_KEY": key}, timeout=(5, 25))
        if response.status_code in (401, 403):
            return _error("KRX 인증키가 거부되었습니다. 키 상태와 해당 서비스의 이용 신청 승인 여부를 확인하세요.", 503)
        if response.status_code == 429:
            return _error("KRX 호출 한도를 초과했습니다. 잠시 후 다시 시도하세요.", 503)
        if response.status_code != 200:
            return _error("KRX 서비스에 연결할 수 없습니다. 잠시 후 다시 시도하세요.", 502)
        body = response.json()
        rows = body.get("OutBlock_1") if isinstance(body, dict) else None
        if rows is None:
            return _error("KRX 응답 형식이 예상과 다릅니다. 인증키·서비스 이용 신청 상태를 확인하세요.", 502)
        rows = [_normalize(row) for row in rows if isinstance(row, dict)]
        with _lock:
            if len(_cache) >= 64:
                _cache.clear()
            _cache[cache_key] = (monotonic(), rows)
        return rows
    except (requests.RequestException, ValueError, AttributeError, TypeError):
        return _error("KRX 응답을 가져오지 못했습니다. 잠시 후 다시 시도하세요.", 503)


def _result(bas_dd: str, **extra):
    return {"source": _SOURCE, "bas_dd": bas_dd, "fetched_at": datetime.now(timezone.utc).isoformat(),
            "cached_for_seconds": _CACHE_SECONDS, **extra}


_DATE = Query(None, pattern=r"^\d{8}$", description="기준일 YYYYMMDD. 비우면 전 영업일(주말 제외)")
_MARKET = Query("KOSPI", pattern=r"^(KOSPI|KOSDAQ|KONEX)$")


@router.get("/stock")
def stock(symbol: str = Query("005930", pattern=r"^\d{6}$"), market: str = _MARKET, bas_dd: str | None = _DATE):
    bas_dd = bas_dd or default_base_date()
    rows = _fetch(MARKETS[market][0], bas_dd)
    if isinstance(rows, JSONResponse):
        return rows
    row = next((r for r in rows if r.get("ISU_CD") == symbol), None)
    if row is None:
        if not rows:
            return _error("해당 기준일의 매매정보가 없습니다. 휴장일이거나 아직 집계 전일 수 있으니 날짜를 바꿔 보세요.", 404)
        return _error(f"{market} 일별매매정보에 종목 {symbol} 이 없습니다. 시장 구분을 바꿔 보세요.", 404)
    return {"ok": True, "result": _result(bas_dd, market=market, symbol=symbol, stock=row, market_rows=len(rows), status="complete")}


@router.get("/market")
def market_top(market: str = _MARKET, bas_dd: str | None = _DATE, limit: int = Query(20, ge=1, le=100),
               sort: str = Query("MKTCAP", pattern=r"^(MKTCAP|ACC_TRDVAL|ACC_TRDVOL|FLUC_RT)$")):
    bas_dd = bas_dd or default_base_date()
    rows = _fetch(MARKETS[market][0], bas_dd)
    if isinstance(rows, JSONResponse):
        return rows
    if not rows:
        return _error("해당 기준일의 매매정보가 없습니다. 휴장일이거나 아직 집계 전일 수 있으니 날짜를 바꿔 보세요.", 404)
    ranked = sorted(rows, key=lambda r: (r.get(sort) is None, -(r.get(sort) or 0)))[:limit]
    return {"ok": True, "result": _result(bas_dd, market=market, sort=sort, total_rows=len(rows), stocks=ranked, status="complete")}


@router.get("/base-info")
def base_info(symbol: str = Query("005930", pattern=r"^\d{6}$"), market: str = _MARKET, bas_dd: str | None = _DATE):
    bas_dd = bas_dd or default_base_date()
    rows = _fetch(MARKETS[market][1], bas_dd)
    if isinstance(rows, JSONResponse):
        return rows
    row = next((r for r in rows if r.get("ISU_SRT_CD") == symbol), None)
    if row is None:
        return _error(f"{market} 종목기본정보에 종목 {symbol} 이 없습니다. 시장 구분이나 기준일을 바꿔 보세요.", 404)
    return {"ok": True, "result": _result(bas_dd, market=market, symbol=symbol, info=row, status="complete")}


@router.get("/index")
def index(service: str = Query("KOSPI", pattern=r"^(KRX|KOSPI|KOSDAQ)$"), bas_dd: str | None = _DATE):
    bas_dd = bas_dd or default_base_date()
    rows = _fetch(INDEX_SERVICES[service], bas_dd)
    if isinstance(rows, JSONResponse):
        return rows
    if not rows:
        return _error("해당 기준일의 지수 정보가 없습니다. 휴장일이거나 아직 집계 전일 수 있으니 날짜를 바꿔 보세요.", 404)
    headline = next((r for r in rows if r.get("IDX_NM") in ("코스피", "코스닥", "KRX 300")), rows[0])
    return {"ok": True, "result": _result(bas_dd, service=service, headline=headline, indices=rows, status="complete")}
