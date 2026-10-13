"""외부 연동용 Open API (/openapi/v1/ohlcv/*).

원본 ``app.api.routes.openapi`` 에서 OHLCV 엔드포인트와 인증 의존성만 남겼다.
조회(search/tickers/{ticker_code})는 공개(IP 호출 제한), 적재(ingest)는 Bearer API 키가 필요하다.
"""

from __future__ import annotations

import logging
import re
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query, Request
from sqlalchemy.exc import SQLAlchemyError

from pgstock.errors import ApiError
from pgstock.parsing import clamp, parse_int
from pgstock.services import ohlcv_ingest as ohlcv_ingest_service
from pgstock.services import ohlcv_store
from pgstock.services.openapi_auth import (
    PUBLIC_RATE_MAX,
    RATE_LIMIT_MAX,
    check_public_rate_limit,
    check_rate_limit,
    resolve_api_key,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/openapi/v1", tags=["openapi"])
_TICKER_CODE = re.compile(r"^[0-9A-Za-z._-]{1,20}$")


def authenticate_api_key(request: Request) -> tuple[int, int]:
    """Bearer API 키를 검증해 (api_key_id, member_id)를 돌려준다. 분당 호출 제한 포함."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise ApiError(401, error="UNAUTHORIZED", message="Authorization: Bearer <api_key> 헤더가 필요합니다.")
    raw_key = auth[len("Bearer "):].strip()
    if not raw_key:
        raise ApiError(401, error="UNAUTHORIZED", message="API 키가 비어 있습니다.")
    resolved = resolve_api_key(raw_key)
    if not resolved:
        raise ApiError(401, error="UNAUTHORIZED", message="유효하지 않거나 폐기된 API 키입니다.")
    api_key_id, member_id = resolved
    if not check_rate_limit(api_key_id):
        raise ApiError(429, error="RATE_LIMITED", message=f"분당 {RATE_LIMIT_MAX}회 호출 제한을 초과했습니다.")
    return api_key_id, member_id


def require_api_key(request: Request) -> int:
    return authenticate_api_key(request)[1]


ApiKeyMember = Annotated[int, Depends(require_api_key)]


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def public_endpoint(request: Request) -> None:
    """인증 없이 누구나 호출할 수 있는 공개 엔드포인트. IP 단위 호출 제한만 둔다."""
    if not check_public_rate_limit(_client_ip(request)):
        raise ApiError(429, error="RATE_LIMITED", message=f"분당 {PUBLIC_RATE_MAX}회 호출 제한을 초과했습니다.")


def _bounded_int(raw: str, name: str, default: int, minimum: int, maximum: int) -> int:
    value = parse_int(raw if raw != "" else default)
    if value is None:
        raise ValueError(f"{name}은 {minimum}~{maximum} 범위의 정수여야 합니다.")
    return clamp(value, minimum, maximum)


def _date_arg(raw: str, name: str) -> date | None:
    raw = raw.strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        raise ValueError(f"{name}은 YYYY-MM-DD 형식이어야 합니다.")


@router.get("/ohlcv/search", dependencies=[Depends(public_endpoint)])
def ohlcv_search(q: str = Query(..., min_length=1), limit: str = Query("10")) -> dict:
    """종목코드/종목명으로 수집된 종목을 찾는다 — 종목 검색 자동완성용."""
    try:
        limit_value = _bounded_int(limit, "limit", 10, 1, 50)
    except (ValueError, TypeError):
        raise ApiError(400, error="INVALID_REQUEST", message="limit 조건을 확인하세요.")
    try:
        rows = ohlcv_store.search_tickers(query=q, limit=limit_value)
    except SQLAlchemyError:
        raise ApiError(503, error="OHLCV_UNAVAILABLE", message="OHLCV 저장소를 조회할 수 없습니다.")
    return {"tickers": rows, "count": len(rows)}


@router.post("/ohlcv/ingest")
def ohlcv_ingest(_: ApiKeyMember, payload: dict = Body(default_factory=dict)) -> dict:
    """종목 하나의 일봉을 공급자에서 받아 OHLCV 저장소를 채운다(멱등). 쓰기라서 API 키가 필요하다."""
    symbol = str(payload.get("symbol") or "").strip()
    if not symbol:
        raise ApiError(400, error="INVALID_REQUEST", message="symbol 이 필요합니다.")
    name = str(payload.get("name") or "").strip()
    try:
        start = _date_arg(str(payload.get("start") or ""), "start")
        end = _date_arg(str(payload.get("end") or ""), "end")
        return ohlcv_ingest_service.ingest(symbol=symbol, name=name, start=start, end=end)
    except ValueError as exc:
        raise ApiError(400, error="INVALID_REQUEST", message=str(exc))
    except SQLAlchemyError:
        raise ApiError(503, error="OHLCV_UNAVAILABLE", message="OHLCV 저장소에 적재할 수 없습니다.")
    except Exception as exc:
        logger.exception("OHLCV 적재 실패 %s", symbol)
        raise ApiError(502, error="OHLCV_INGEST_FAILED", message=f"시세 공급자 조회에 실패했습니다: {exc}")


@router.get("/ohlcv/tickers", dependencies=[Depends(public_endpoint)])
def ohlcv_tickers(q: str = Query(""), market: str = Query(""), year: str = Query(""),
                  limit: str = Query("100"), offset: str = Query("0")) -> dict:
    """OHLCV 데이터가 수집된 종목을 탐색한다."""
    try:
        limit_value = _bounded_int(limit, "limit", 100, 1, 200)
        offset_value = _bounded_int(offset, "offset", 0, 0, 10_000_000)
        year_number = None
        if year.strip():
            year_number = int(year)
            if year_number < 1990 or year_number > date.today().year + 1:
                raise ValueError("year 범위가 올바르지 않습니다.")
        return ohlcv_store.public_tickers(query=q.strip(), market=market.strip(), year=year_number,
                                          limit=limit_value, offset=offset_value)
    except (ValueError, TypeError):
        raise ApiError(400, error="INVALID_REQUEST", message="year 및 페이지 조건을 확인하세요.")
    except SQLAlchemyError:
        raise ApiError(503, error="OHLCV_UNAVAILABLE", message="OHLCV 저장소를 조회할 수 없습니다.")


@router.get("/ohlcv/{ticker_code}", dependencies=[Depends(public_endpoint)])
def ohlcv_history(ticker_code: str, limit: str = Query("250"), offset: str = Query("0"), order: str = Query("asc"),
                  date_from: str = Query(""), date_to: str = Query(""), year: str = Query("")) -> dict:
    """종목 하나의 일별 OHLCV를 연도/날짜 범위로 페이지 조회한다."""
    code = ticker_code.upper().strip()
    if not _TICKER_CODE.fullmatch(code):
        raise ApiError(400, error="INVALID_REQUEST", message="ticker_code 형식이 올바르지 않습니다.")
    try:
        limit_value = _bounded_int(limit, "limit", 250, 1, 1000)
        offset_value = _bounded_int(offset, "offset", 0, 0, 10_000_000)
        order_value = order.strip().lower()
        if order_value not in {"asc", "desc"}:
            raise ValueError("order는 asc 또는 desc여야 합니다.")
        from_date = _date_arg(date_from, "date_from")
        to_date = _date_arg(date_to, "date_to")
        year_number = int(year) if year.strip() else None
        if year_number is not None:
            if year_number < 1990 or year_number > date.today().year + 1:
                raise ValueError("year 범위가 올바르지 않습니다.")
            from_date = max(from_date or date(year_number, 1, 1), date(year_number, 1, 1))
            to_date = min(to_date or date(year_number, 12, 31), date(year_number, 12, 31))
        elif from_date is None and to_date is None:
            year_number = date.today().year
            from_date, to_date = date(year_number, 1, 1), date(year_number, 12, 31)
        if from_date and to_date and from_date > to_date:
            raise ValueError("date_from은 date_to보다 늦을 수 없습니다.")
        result = ohlcv_store.public_history(code=code, date_from=from_date, date_to=to_date, order=order_value,
                                            limit=limit_value, offset=offset_value)
    except (ValueError, TypeError) as exc:
        raise ApiError(400, error="INVALID_REQUEST", message=str(exc))
    except SQLAlchemyError:
        raise ApiError(503, error="OHLCV_UNAVAILABLE", message="OHLCV 저장소를 조회할 수 없습니다.")
    if result is None:
        raise ApiError(404, error="NOT_FOUND", message="OHLCV 종목을 찾을 수 없습니다.")
    result["filters"] = {"year": year_number, "dateFrom": from_date.isoformat() if from_date else None,
                         "dateTo": to_date.isoformat() if to_date else None, "order": order_value}
    return result
