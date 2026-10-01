"""``*_aws`` 병행 트랙이 쓰는 AWS Secrets Manager 자격증명 소스.

증권사별로 JSON 보안 암호 하나를 둔다: ``stock-coin-trade/kis``, ``stock-coin-trade/kb``,
``stock-coin-trade/alpaca``. 값은 서버에서만 복호화해 잠시 메모리에 캐시하며 브라우저·로그에는 내보내지 않는다.
"""

from __future__ import annotations

import json
import threading
import time
from typing import Any

from app.core.config import get_settings

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError, NoRegionError
except ImportError:  # pragma: no cover - boto3 미설치 환경
    boto3 = None
    BotoCoreError = ClientError = NoRegionError = Exception


class AwsSecretError(RuntimeError):
    """비밀 값을 절대 포함하지 않는 사용자 안전 오류."""


_CACHE_TTL_SECONDS = 300
_client_lock = threading.Lock()
_client: Any = None
_cache: dict[str, dict[str, Any]] = {}
_cache_lock = threading.Lock()


def _prefix() -> str:
    return get_settings().aws_secrets_manager_prefix.strip("/")


def _region() -> str | None:
    return get_settings().aws_region


def full_secret_name(service: str) -> str:
    return f"{_prefix()}/{service.strip('/')}"


def full_parameter_name(name: str) -> str:
    """이전 호출자를 위한 표시용 헬퍼."""
    service, _, field = name.strip("/").partition("/")
    return f"{full_secret_name(service)}#{field}" if field else full_secret_name(service)


def _secrets_client():
    global _client
    if boto3 is None:
        raise AwsSecretError("boto3가 설치되지 않았습니다. 의존성을 다시 설치하세요(uv sync).")
    with _client_lock:
        if _client is None:
            region = _region()
            _client = boto3.client("secretsmanager", region_name=region) if region else boto3.client("secretsmanager")
        return _client


def _error_code(exc: Exception) -> str:
    return getattr(exc, "response", {}).get("Error", {}).get("Code", "")


def get_secret(service: str) -> dict[str, str]:
    secret_name = full_secret_name(service)
    with _cache_lock:
        cached = _cache.get(secret_name)
        if cached and cached["expires_at"] > time.time():
            return cached["value"]
    try:
        response = _secrets_client().get_secret_value(SecretId=secret_name)
    except AwsSecretError:
        raise
    except NoRegionError as exc:
        raise AwsSecretError("AWS 리전이 설정되지 않았습니다. AWS_REGION을 설정하세요.") from exc
    except (BotoCoreError, ClientError) as exc:
        code = _error_code(exc)
        if code == "ResourceNotFoundException":
            raise AwsSecretError(f"AWS Secrets Manager에 {secret_name} 보안 암호가 없습니다. 먼저 생성하세요.") from exc
        raise AwsSecretError(f"AWS Secrets Manager 조회에 실패했습니다: {code or exc.__class__.__name__}") from exc

    raw = response.get("SecretString")
    try:
        value = json.loads(raw or "")
    except (TypeError, json.JSONDecodeError) as exc:
        raise AwsSecretError(f"{secret_name}은 JSON 보안 암호여야 합니다.") from exc
    if not isinstance(value, dict):
        raise AwsSecretError(f"{secret_name}의 JSON 형식이 올바르지 않습니다.")
    normalized = {str(key): str(item).strip() for key, item in value.items() if item is not None}
    with _cache_lock:
        _cache[secret_name] = {"value": normalized, "expires_at": time.time() + _CACHE_TTL_SECONDS}
    return normalized


def get_parameter(name: str, *, required: bool = True) -> str | None:
    """``kis/account``는 보안 암호 ``kis``의 ``account`` 필드를 읽는다."""
    service, separator, field = name.strip("/").partition("/")
    if not separator:
        raise AwsSecretError("보안 암호 필드 경로가 올바르지 않습니다.")
    value = get_secret(service).get(field)
    if not value and required:
        raise AwsSecretError(f"AWS Secrets Manager의 {full_secret_name(service)}에 {field} 필드가 없습니다.")
    return value or None


def get_credentials(prefix: str, *, key_name: str = "app_key", secret_name: str = "secret") -> tuple[str, str]:
    document = get_secret(prefix)
    app_key = document.get(key_name)
    app_secret = document.get(secret_name)
    if not app_key or not app_secret:
        raise AwsSecretError(f"AWS Secrets Manager의 {full_secret_name(prefix)}에 {key_name}, {secret_name} 필드가 필요합니다.")
    return app_key, app_secret


def inspect_secrets(requirements: dict[str, tuple[str, ...]]) -> dict[str, Any]:
    """필드 값은 돌려주지 않고 준비 상태와 필드 이름만 반환한다."""
    secrets = []
    for service, required_fields in requirements.items():
        secret_name = full_secret_name(service)
        try:
            item = _secrets_client().describe_secret(SecretId=secret_name)
            document = get_secret(service)
            missing_fields = [field for field in required_fields if not document.get(field)]
            secrets.append({
                "name": secret_name,
                "configured": not missing_fields,
                "requiredFields": list(required_fields),
                "missingFields": missing_fields,
                "description": item.get("Description"),
                "lastChangedAt": item.get("LastChangedDate").isoformat() if item.get("LastChangedDate") else None,
                "rotationEnabled": bool(item.get("RotationEnabled")),
            })
        except NoRegionError as exc:
            raise AwsSecretError("AWS 리전이 설정되지 않았습니다. AWS_REGION을 설정하세요.") from exc
        except (BotoCoreError, ClientError) as exc:
            code = _error_code(exc)
            if code == "ResourceNotFoundException":
                secrets.append({"name": secret_name, "configured": False})
                continue
            raise AwsSecretError(f"AWS Secrets Manager 상태 조회에 실패했습니다: {code or exc.__class__.__name__}") from exc
    return {
        "provider": "AWS Secrets Manager",
        "region": _region() or "AWS SDK default chain",
        "secretPrefix": _prefix(),
        "secrets": secrets,
        "configuredCount": sum(1 for item in secrets if item["configured"]),
        "requiredCount": len(secrets),
    }
