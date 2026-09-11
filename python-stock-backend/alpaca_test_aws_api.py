import requests

from flask import Blueprint, jsonify, request

from aws_secret_store import AwsSecretError
from alpaca_test_aws import test_paper_account_aws, test_paper_asset_aws, test_paper_clock_aws, test_paper_positions_aws


aws_alpaca_test_bp = Blueprint("aws_alpaca_test", __name__, url_prefix="/api/aws-alpaca-test")


def _run(build):
    try:
        return jsonify({"ok": True, "result": build()})
    except AwsSecretError as exc:
        # A rejected key/parameter is an expected test result, not a browser error.
        return jsonify({"ok": False, "message": str(exc)})
    except requests.RequestException:
        return jsonify({"ok": False, "message": "Alpaca 서버 연결에 실패했습니다. 잠시 후 다시 시도하세요."}), 503


@aws_alpaca_test_bp.get("/paper/account")
def paper_account():
    return _run(test_paper_account_aws)


@aws_alpaca_test_bp.get("/paper/positions")
def paper_positions():
    return _run(test_paper_positions_aws)


@aws_alpaca_test_bp.get("/paper/clock")
def paper_clock():
    return _run(test_paper_clock_aws)


@aws_alpaca_test_bp.get("/paper/asset")
def paper_asset():
    symbol = request.args.get("symbol", "AAPL").strip().upper()
    if not symbol.isalpha() or not 1 <= len(symbol) <= 10:
        return jsonify({"ok": False, "message": "종목 심볼은 영문 1~10자로 입력하세요."}), 400
    return _run(lambda: test_paper_asset_aws(symbol))
