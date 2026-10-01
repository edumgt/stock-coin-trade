"""KB증권 Open API 인증 토큰 발급을 안전하게 점검하는 읽기 전용 스크립트.

사용법: python -m app.cli.kb_token_test

저장소 루트 ``.env``의 KB_APP_KEY/KB_APP_SECRET만 사용합니다.
AppKey, Secret, Access Token은 출력하거나 저장하지 않습니다.
"""

from __future__ import annotations

import os

import requests

import app.core.config  # noqa: F401 - 저장소 루트 .env를 프로세스 환경에 올린다.

KB_API_BASE_URL = "https://developer.kbsec.com:32484"
TOKEN_PATH = "/oauth2/token"


def load_credentials() -> tuple[str, str]:
    app_key = os.environ.get("KB_APP_KEY")
    app_secret = os.environ.get("KB_APP_SECRET")
    if app_key and app_secret:
        return app_key, app_secret
    raise RuntimeError(".env에 KB_APP_KEY와 KB_APP_SECRET을 설정하세요.")


def request_access_token() -> tuple[str, int]:
    """토큰을 요청해 유형과 만료 시간만 돌려준다. 값은 절대 반환하지 않는다."""
    app_key, app_secret = load_credentials()
    response = requests.post(
        f"{KB_API_BASE_URL}{TOKEN_PATH}",
        headers={"Content-Type": "application/json"},
        json={
            "dataHeader": {"ipAddr": "", "macAddr": ""},
            "dataBody": {"appKey": app_key, "appSecret": app_secret, "grantType": "client_credentials"},
        },
        timeout=20,
    )
    body = response.json()
    token = body.get("access_token") or body.get("dataBody", {}).get("access_token")
    if not token:
        header = body.get("dataHeader", {})
        code = header.get("processCode") or body.get("error") or body.get("code") or "unknown"
        message = header.get("processMessage") or body.get("error_description") or body.get("message")
        raise RuntimeError(f"KB 토큰 발급 실패 (HTTP {response.status_code}, {code}): {message}")

    token_type = body.get("token_type") or body.get("dataBody", {}).get("token_type") or "Bearer"
    expires_in = body.get("expires_in") or body.get("dataBody", {}).get("expires_in") or 0
    return token_type, int(expires_in)


def main() -> int:
    try:
        token_type, expires_in = request_access_token()
    except (requests.RequestException, RuntimeError, ValueError) as exc:
        print(f"KB Open API 토큰 발급 점검 실패: {exc}")
        return 1
    print(f"KB Open API 토큰 발급 성공 | 유형={token_type} | 유효기간(초)={expires_in}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
