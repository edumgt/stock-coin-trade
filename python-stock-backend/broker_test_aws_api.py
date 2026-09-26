import requests

from flask import Blueprint, jsonify, request, session

from authz import can_use_kis_account
from aws_secret_store import AwsSecretError, inspect_secrets
from broker_test_aws import (
    check_kb_token_aws,
    get_kb_domestic_quote_aws,
    get_kis_balance_aws,
    get_kis_quote_aws,
)


aws_broker_test_bp = Blueprint("aws_broker_test", __name__, url_prefix="/api/aws-broker-test")

_REQUIRED_SECRETS = {
    "kis": ("app_key", "secret", "account"),
    "kb": ("app_key", "secret"),
    "alpaca": ("api_key", "secret_key"),
}


def _symbol() -> str:
    symbol = request.args.get("symbol", "005930").strip()
    if len(symbol) != 6 or not symbol.isdigit():
        raise AwsSecretError("종목코드는 6자리 KRX 숫자 코드여야 합니다.")
    return symbol


def _run(broker: str, build):
    try:
        return jsonify({"ok": True, **build()})
    except AwsSecretError as exc:
        # A rejected key/parameter is an expected test result, not a browser
        # transport failure. Returning 200 prevents an unnecessary console 502.
        return jsonify({"ok": False, "broker": broker, "message": str(exc)})
    except requests.RequestException:
        return jsonify({"ok": False, "broker": broker, "message": f"{broker} 서버 연결에 실패했습니다. 잠시 후 다시 시도하세요."}), 503


@aws_broker_test_bp.get("/secrets/status")
def secrets_status():
    """Secrets Manager field check; SecretString values are never returned."""
    return _run("AWS Secrets Manager", lambda: {"status": inspect_secrets(_REQUIRED_SECRETS)})


@aws_broker_test_bp.get("/kis/quote")
def kis_quote():
    return _run("한국투자증권 Testbed (AWS Secrets Manager)", lambda: {"quote": get_kis_quote_aws(_symbol())})


@aws_broker_test_bp.get("/kis/balance")
def kis_balance():
    if not can_use_kis_account(session.get("member_id")):
        return jsonify({"ok": False, "message": "KIS 모의계좌 잔고는 로그인 후 조회할 수 있습니다."}), 401
    return _run("한국투자증권 Testbed (AWS Secrets Manager)", lambda: {"balance": get_kis_balance_aws()})


@aws_broker_test_bp.get("/kb/token")
def kb_token():
    return _run("KB증권 Open API (AWS Secrets Manager)", lambda: {"check": check_kb_token_aws()})


@aws_broker_test_bp.get("/kb/quote")
def kb_quote():
    return _run("KB증권 Open API (AWS Secrets Manager)", lambda: {"quote": get_kb_domestic_quote_aws(_symbol())})
