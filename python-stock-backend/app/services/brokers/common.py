"""증권사 게이트웨이 공통: 오류 타입, 자격증명 출처, 응답 파싱.

자격증명은 호출 시점에 환경변수(.env) 또는 AWS Secrets Manager에서 읽는다(app.core.config 참고).
"""

from __future__ import annotations

import os
from typing import Any

import requests


class BrokerApiError(RuntimeError):
    """자격증명·접근 토큰을 절대 포함하지 않는 사용자 안전 오류."""

    def __init__(self, message: str, status_code: int = 502, code: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.code = code


def credential_source() -> str:
    """서버(EC2)는 .env의 ``CREDENTIAL_SOURCE=aws``로 AWS Secrets Manager를, 로컬은 .env 환경변수를 쓴다."""
    raw = os.environ.get("CREDENTIAL_SOURCE", "").strip().lower()
    if raw in ("aws", "sm", "secrets-manager", "secretsmanager", "secrets_manager"):
        return "aws"
    return "env"


def aws_credentials(service: str, **kwargs: str) -> tuple[str, str]:
    try:
        from app.services.aws_secret_store import AwsSecretError, get_credentials
    except Exception as exc:  # boto3 미설치 등
        raise BrokerApiError("AWS Secrets Manager 연동 모듈을 불러오지 못했습니다.", 503) from exc
    try:
        return get_credentials(service, **kwargs)
    except AwsSecretError as exc:
        raise BrokerApiError(str(exc), 503) from exc


def env_credentials(prefix: str) -> tuple[str, str]:
    if credential_source() == "aws":
        return aws_credentials(prefix.lower())
    app_key = os.environ.get(f"{prefix}_APP_KEY", "").strip()
    app_secret = os.environ.get(f"{prefix}_APP_SECRET", "").strip()
    if not app_key or not app_secret:
        raise BrokerApiError(f".env에 {prefix}_APP_KEY와 {prefix}_APP_SECRET을 모두 설정하세요.", 503)
    return app_key, app_secret


def json_body(response: requests.Response, broker: str) -> dict[str, Any]:
    try:
        return response.json()
    except ValueError as exc:
        raise BrokerApiError(f"{broker} 서버가 JSON 응답을 반환하지 않았습니다. (HTTP {response.status_code})") from exc
