"""KB증권 Open API 인증 토큰 발급을 안전하게 점검하는 읽기 전용 스크립트.

사용법: python kb_token_test.py

KB_APP_KEY/KB_APP_SECRET 환경변수를 우선 사용하며, 없을 때만 프로젝트 루트의
gitignore 대상 파일 kb.key를 읽습니다. AppKey, Secret, Access Token은
출력하거나 저장하지 않습니다.
"""

from __future__ import annotations

import os
from pathlib import Path

import requests


KB_API_BASE_URL = "https://developer.kbsec.com:32484"
TOKEN_PATH = "/oauth2/token"


def _read_key_file(path: Path) -> tuple[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if "=" not in raw_line:
            continue
        name, value = raw_line.split("=", 1)
        values[name.strip().lower()] = value.strip()

    app_key = values.get("appkey") or values.get("app_key")
    app_secret = values.get("secret") or values.get("appsecret") or values.get("app_secret")
    if not app_key or not app_secret:
        raise RuntimeError("kb.key에 AppKey와 Secret을 설정하세요.")
    return app_key, app_secret


def load_credentials() -> tuple[str, str]:
    app_key = os.environ.get("KB_APP_KEY")
    app_secret = os.environ.get("KB_APP_SECRET")
    if app_key and app_secret:
        return app_key, app_secret

    key_file = Path(__file__).resolve().parents[1] / "kb.key"
    if not key_file.is_file():
        raise RuntimeError("KB_APP_KEY/KB_APP_SECRET 또는 프로젝트 루트의 kb.key가 필요합니다.")
    return _read_key_file(key_file)


def request_access_token() -> tuple[str, int]:
    """Request a token and return only its type and expiry; never return the value."""
    app_key, app_secret = load_credentials()
    response = requests.post(
        f"{KB_API_BASE_URL}{TOKEN_PATH}",
        headers={"Content-Type": "application/json"},
        json={
            "dataHeader": {"ipAddr": "", "macAddr": ""},
            "dataBody": {
                "appKey": app_key,
                "appSecret": app_secret,
                "grantType": "client_credentials",
            },
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
