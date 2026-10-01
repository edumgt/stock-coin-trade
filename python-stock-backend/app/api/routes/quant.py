"""퀀트 데이터 브라우저·백테스트·팩터 분석 API."""

from __future__ import annotations

from fastapi import APIRouter, Body, Query
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.core.errors import ApiError
from app.core.parsing import clamp, parse_float, parse_int
from app.services import quant

from ..schemas import BacktestBody

router = APIRouter(prefix="/api/quant", tags=["quant"])


@router.get("/overview")
def overview() -> dict:
    try:
        return quant.overview()
    except SQLAlchemyError as exc:
        raise ApiError(503, message=f"퀀트 PostgreSQL에 연결할 수 없습니다: {exc.__class__.__name__}")


@router.get("/market-data")
def market_data(symbol: str = Query("005930"), limit: int = Query(100)) -> dict:
    try:
        return {"rows": quant.market_data(quant.validate_symbol(symbol), clamp(limit, 1, 500)), "source": "PostgreSQL market_data"}
    except ValueError as exc:
        raise ApiError(400, message=str(exc))
    except SQLAlchemyError as exc:
        raise ApiError(503, message=f"데이터 조회 실패: {exc.__class__.__name__}")


@router.get("/signals")
def signals(symbol: str = Query("005930"), limit: int = Query(100), fast: int = Query(20), slow: int = Query(50)) -> dict:
    try:
        fast_value = clamp(fast, 2, 100)
        slow_value = max(fast_value + 1, min(slow, 250))
        rows = quant.signals(quant.validate_symbol(symbol), clamp(limit, 1, 500), fast_value, slow_value)
        return {"rows": rows, "fast": fast_value, "slow": slow_value}
    except (ValueError, SQLAlchemyError) as exc:
        raise ApiError(400, message=f"시그널 조회 실패: {exc}")


@router.post("/backtests")
def run_backtest(payload: BacktestBody = Body(default_factory=BacktestBody)):
    symbol = str(payload.symbol or "005930").upper().strip()
    fast = parse_int(payload.fast)
    slow = parse_int(payload.slow)
    quantity = parse_int(payload.quantity)
    fee_rate = parse_float(payload.feeRate)
    slippage = parse_float(payload.slippage)
    strategy = str(payload.strategy or "ma2050").strip().lower()
    if None in (fast, slow, quantity, fee_rate, slippage):
        raise ApiError(400, message="symbol과 이동평균 기간을 확인하세요.")
    quantity = clamp(quantity, 1, 100000)
    fee_rate = max(0.0, min(fee_rate, 0.02))
    slippage = max(0.0, min(slippage, 0.02))
    if not symbol or fast < 2 or slow <= fast or slow > 250 or strategy not in quant.STRATEGY_NAMES:
        raise ApiError(400, message="symbol과 이동평균 기간을 확인하세요.")
    try:
        result = quant.run_backtest(payload.model_dump(exclude_unset=True), symbol=symbol, fast=fast, slow=slow,
                                    quantity=quantity, fee_rate=fee_rate, slippage=slippage, strategy=strategy)
    except (ValueError, SQLAlchemyError) as exc:
        raise ApiError(400, message=f"백테스트 실행 실패: {exc}")
    return JSONResponse(result, status_code=201)


@router.get("/results")
def results() -> dict:
    try:
        return quant.results()
    except SQLAlchemyError as exc:
        raise ApiError(503, message=f"결과 조회 실패: {exc.__class__.__name__}")


@router.get("/factor-analysis")
def factor_analysis(symbol: str = Query("005930")) -> dict:
    """일간 수익률로 CAPM 알파/베타와 Fama-French 스타일 노출을 계산한다."""
    try:
        result = quant.factor_analysis(quant.validate_symbol(symbol))
    except (ValueError, SQLAlchemyError) as exc:
        raise ApiError(400, message=f"팩터 분석 실패: {exc}")
    if result is None:
        raise ApiError(400, message="팩터 분석에는 최소 60개 이상의 가격 관측치가 필요합니다.")
    return result
