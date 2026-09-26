"""KIS 모의투자 Testbed의 국내주식 현재가를 읽기 전용으로 확인하는 스크립트.

사용법:
    python kis_quote_test.py --symbol 005930

키는 저장소 루트 ``.env``의 KIS_PAPER_APP_KEY/KIS_PAPER_APP_SECRET만
사용합니다. 키와 토큰은 절대로 출력하거나 파일로 저장하지 않습니다.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import requests
from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)


TESTBED_URL = "https://openapivts.koreainvestment.com:29443"
TOKEN_PATH = "/oauth2/tokenP"
QUOTE_PATH = "/uapi/domestic-stock/v1/quotations/inquire-price"
QUOTE_TR_ID = "FHKST01010100"


def load_credentials() -> tuple[str, str]:
    app_key = os.environ.get("KIS_PAPER_APP_KEY")
    app_secret = os.environ.get("KIS_PAPER_APP_SECRET")
    if app_key and app_secret:
        return app_key, app_secret
    raise RuntimeError(".env에 KIS_PAPER_APP_KEY와 KIS_PAPER_APP_SECRET을 설정하세요.")


def get_mock_quote(symbol: str) -> dict[str, str]:
    """Fetch one current quote from Testbed; no account or order API is used."""
    app_key, app_secret = load_credentials()
    token_response = requests.post(
        f"{TESTBED_URL}{TOKEN_PATH}",
        headers={"content-type": "application/json; charset=utf-8"},
        json={"grant_type": "client_credentials", "appkey": app_key, "appsecret": app_secret},
        timeout=15,
    )
    token_body = token_response.json()
    access_token = token_body.get("access_token")
    if not access_token:
        message = token_body.get("error_description") or token_body.get("msg1") or "토큰 발급 실패"
        raise RuntimeError(f"KIS 토큰 발급 실패 (HTTP {token_response.status_code}): {message}")

    quote_response = requests.get(
        f"{TESTBED_URL}{QUOTE_PATH}",
        headers={
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {access_token}",
            "appkey": app_key,
            "appsecret": app_secret,
            "tr_id": QUOTE_TR_ID,
        },
        params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": symbol},
        timeout=15,
    )
    quote_body = quote_response.json()
    if quote_body.get("rt_cd") != "0":
        raise RuntimeError(
            f"KIS 시세 조회 실패 (HTTP {quote_response.status_code}, "
            f"{quote_body.get('msg_cd')}): {quote_body.get('msg1')}"
        )
    return quote_body["output"]


def main() -> int:
    parser = argparse.ArgumentParser(description="KIS 모의투자 Testbed 현재가 조회")
    parser.add_argument("--symbol", default="005930", help="KRX 6자리 종목코드 (기본값: 005930)")
    args = parser.parse_args()
    symbol = args.symbol.strip()
    if not (len(symbol) == 6 and symbol.isdigit()):
        parser.error("--symbol은 6자리 KRX 종목코드여야 합니다.")

    quote = get_mock_quote(symbol)
    print(
        " | ".join(
            [
                f"종목={symbol}",
                f"현재가={quote.get('stck_prpr')}",
                f"전일대비={quote.get('prdy_vrss')}",
                f"등락률={quote.get('prdy_ctrt')}",
                f"누적거래량={quote.get('acml_vol')}",
                f"체결시각={quote.get('stck_cntg_hour')}",
            ]
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
