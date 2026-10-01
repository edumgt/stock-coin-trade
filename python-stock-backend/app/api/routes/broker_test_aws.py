"""AWS Secrets Manager 자격증명 트랙의 KIS/KB 읽기 전용 테스트."""

from __future__ import annotations

import requests
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.core.deps import OptionalMemberId
from app.core.errors import ApiError
from app.services.authz import can_use_kis_account
from app.services.aws_secret_store import AwsSecretError, inspect_secrets
from app.services.brokers.aws import (
    check_kb_token_aws,
    get_kb_domestic_quote_aws,
    get_kis_balance_aws,
    get_kis_quote_aws,
)

router = APIRouter(prefix="/api/aws-broker-test", tags=["broker-test"])

_REQUIRED_SECRETS = {
    "kis": ("app_key", "secret", "account"),
    "kb": ("app_key", "secret"),
    "alpaca": ("api_key", "secret_key"),
}
KIS_BROKER = "한국투자증권 Testbed (AWS Secrets Manager)"
KB_BROKER = "KB증권 Open API (AWS Secrets Manager)"


def _symbol(symbol: str) -> str:
    symbol = symbol.strip()
    if len(symbol) != 6 or not symbol.isdigit():
        raise AwsSecretError("종목코드는 6자리 KRX 숫자 코드여야 합니다.")
    return symbol


def _run(broker: str, build):
    try:
        return {"ok": True, **build()}
    except AwsSecretError as exc:
        # 거부된 키·파라미터는 예상되는 테스트 결과이므로 200으로 돌려 콘솔 502를 피한다.
        return {"ok": False, "broker": broker, "message": str(exc)}
    except requests.RequestException:
        return JSONResponse({"ok": False, "broker": broker, "message": f"{broker} 서버 연결에 실패했습니다. 잠시 후 다시 시도하세요."}, status_code=503)


@router.get("/secrets/status")
def secrets_status():
    """Secrets Manager 필드 점검. SecretString 값은 절대 반환하지 않는다."""
    return _run("AWS Secrets Manager", lambda: {"status": inspect_secrets(_REQUIRED_SECRETS)})


@router.get("/kis/quote")
def kis_quote(symbol: str = Query("005930")):
    return _run(KIS_BROKER, lambda: {"quote": get_kis_quote_aws(_symbol(symbol))})


@router.get("/kis/balance")
def kis_balance(member_id: OptionalMemberId):
    if not can_use_kis_account(member_id):
        raise ApiError(401, ok=False, message="KIS 모의계좌 잔고는 로그인 후 조회할 수 있습니다.")
    return _run(KIS_BROKER, lambda: {"balance": get_kis_balance_aws()})


@router.get("/kb/token")
def kb_token():
    return _run(KB_BROKER, lambda: {"check": check_kb_token_aws()})


@router.get("/kb/quote")
def kb_quote(symbol: str = Query("005930")):
    return _run(KB_BROKER, lambda: {"quote": get_kb_domestic_quote_aws(_symbol(symbol))})
