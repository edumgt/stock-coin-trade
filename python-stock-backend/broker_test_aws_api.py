import requests

from flask import Blueprint, jsonify, request

from aws_secret_store import AwsSecretError, inspect_parameters
from broker_test_aws import (
    check_kb_token_aws,
    get_kb_domestic_quote_aws,
    get_kis_balance_aws,
    get_kis_quote_aws,
)


aws_broker_test_bp = Blueprint("aws_broker_test", __name__, url_prefix="/api/aws-broker-test")

_REQUIRED_PARAMETERS = [
    "kis/app_key", "kis/secret", "kis/account",
    "kb/app_key", "kb/secret",
    "alpaca/api_key", "alpaca/secret_key",
]


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


@aws_broker_test_bp.get("/ssm/status")
def ssm_status():
    """SSM access and parameter existence check; values are never decrypted or returned."""
    return _run("AWS SSM Parameter Store", lambda: {"status": inspect_parameters(_REQUIRED_PARAMETERS)})


@aws_broker_test_bp.get("/kis/quote")
def kis_quote():
    return _run("한국투자증권 Testbed (AWS SSM)", lambda: {"quote": get_kis_quote_aws(_symbol())})


@aws_broker_test_bp.get("/kis/balance")
def kis_balance():
    return _run("한국투자증권 Testbed (AWS SSM)", lambda: {"balance": get_kis_balance_aws()})


@aws_broker_test_bp.get("/kb/token")
def kb_token():
    return _run("KB증권 Open API (AWS SSM)", lambda: {"check": check_kb_token_aws()})


@aws_broker_test_bp.get("/kb/quote")
def kb_quote():
    return _run("KB증권 Open API (AWS SSM)", lambda: {"quote": get_kb_domestic_quote_aws(_symbol())})
