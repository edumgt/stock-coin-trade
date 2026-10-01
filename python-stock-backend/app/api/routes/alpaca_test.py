"""Alpaca Paper Trading 읽기 전용 연결 테스트."""

from __future__ import annotations

import requests
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.core.deps import OptionalMemberId
from app.core.errors import ApiError
from app.services.alpaca.paper import (
    get_alpaca_configuration_status,
    run_paper_order_flow_test,
    test_market_clock,
    test_market_quote,
    test_paper_account,
    test_paper_orders,
    test_paper_positions,
)
from app.services.brokers.common import BrokerApiError

router = APIRouter(prefix="/api/alpaca-test", tags=["alpaca"])


def _run(build):
    try:
        return {"ok": True, "result": build()}
    except BrokerApiError as exc:
        # 자격증명 거부는 예상되는 테스트 결과이므로 브라우저 오류로 만들지 않는다.
        payload = {"ok": False, "message": str(exc)}
        if getattr(exc, "code", ""):
            payload["code"] = exc.code
        return payload
    except requests.RequestException:
        return JSONResponse({"ok": False, "message": "Alpaca 서버 연결에 실패했습니다. 잠시 후 다시 시도하세요."}, status_code=503)


@router.get("/status")
def configuration_status(member_id: OptionalMemberId) -> dict:
    if not member_id:
        raise ApiError(401, ok=False, message="Alpaca 실습은 로그인 후 이용할 수 있습니다.")
    return {"ok": True, "status": get_alpaca_configuration_status()}


@router.get("/paper/account")
def paper_account():
    return _run(test_paper_account)


@router.get("/paper/positions")
def paper_positions():
    return _run(test_paper_positions)


@router.get("/paper/orders")
def paper_orders():
    return _run(test_paper_orders)


@router.get("/market/clock")
def market_clock():
    return _run(test_market_clock)


@router.get("/market/quote")
def market_quote(symbol: str = Query("AAPL")):
    symbol = symbol.strip()
    if not symbol.isalpha() or not (1 <= len(symbol) <= 5):
        return {"ok": False, "message": "symbol은 1~5자리 영문 티커여야 합니다."}
    return _run(lambda: test_market_quote(symbol))


@router.post("/paper/order-flow-test")
def paper_order_flow_test(member_id: OptionalMemberId):
    if not member_id:
        raise ApiError(401, ok=False, message="Paper 주문 흐름 테스트는 로그인 후 실행할 수 있습니다.")
    return _run(run_paper_order_flow_test)
