"""AWS Secrets Manager 자격증명 트랙의 Alpaca Paper 읽기 전용 테스트."""

from __future__ import annotations

import requests
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.core.errors import ApiError
from app.services.alpaca.aws import (
    test_paper_account_aws,
    test_paper_asset_aws,
    test_paper_clock_aws,
    test_paper_positions_aws,
)
from app.services.aws_secret_store import AwsSecretError

router = APIRouter(prefix="/api/aws-alpaca-test", tags=["alpaca"])


def _run(build):
    try:
        return {"ok": True, "result": build()}
    except AwsSecretError as exc:
        return {"ok": False, "message": str(exc)}
    except requests.RequestException:
        return JSONResponse({"ok": False, "message": "Alpaca 서버 연결에 실패했습니다. 잠시 후 다시 시도하세요."}, status_code=503)


@router.get("/paper/account")
def paper_account():
    return _run(test_paper_account_aws)


@router.get("/paper/positions")
def paper_positions():
    return _run(test_paper_positions_aws)


@router.get("/paper/clock")
def paper_clock():
    return _run(test_paper_clock_aws)


@router.get("/paper/asset")
def paper_asset(symbol: str = Query("AAPL")):
    symbol = symbol.strip().upper()
    if not symbol.isalpha() or not 1 <= len(symbol) <= 10:
        raise ApiError(400, ok=False, message="종목 심볼은 영문 1~10자로 입력하세요.")
    return _run(lambda: test_paper_asset_aws(symbol))
