"""AWS Secrets Manager credential source for the parallel ``*_aws`` modules.

Each broker is stored as one JSON secret:
``stock-coin-trade/kis``, ``stock-coin-trade/kb`` and
``stock-coin-trade/alpaca``. Values are decrypted only on the server, cached
briefly in memory, and never returned to the browser or logs.
"""
from __future__ import annotations

import json
import os
import threading
import time
from typing import Any

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError, NoRegionError
except ImportError:
    boto3 = None
    BotoCoreError = ClientError = NoRegionError = Exception


class AwsSecretError(RuntimeError):
    """A user-safe error that never includes secret values."""


_SECRET_PREFIX = os.environ.get("AWS_SECRETS_MANAGER_PREFIX", "stock-coin-trade").strip("/")
_REGION = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
_CACHE_TTL_SECONDS = 300
_client_lock = threading.Lock()
_client: Any = None
_cache: dict[str, dict[str, Any]] = {}
_cache_lock = threading.Lock()


def full_secret_name(service: str) -> str:
    return f"{_SECRET_PREFIX}/{service.strip('/')}"


def full_parameter_name(name: str) -> str:
    """Compatibility display helper for older callers."""
    service, _, field = name.strip("/").partition("/")
    return f"{full_secret_name(service)}#{field}" if field else full_secret_name(service)


def _secrets_client():
    global _client
    if boto3 is None:
        raise AwsSecretError("boto3가 설치되지 않았습니다. requirements.txt를 다시 설치하세요.")
    with _client_lock:
        if _client is None:
            _client = boto3.client("secretsmanager", region_name=_REGION) if _REGION else boto3.client("secretsmanager")
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
    """Compatibility accessor: ``kis/account`` reads field ``account`` from secret ``kis``."""
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
        raise AwsSecretError(
            f"AWS Secrets Manager의 {full_secret_name(prefix)}에 {key_name}, {secret_name} 필드가 필요합니다."
        )
    return app_key, app_secret


def inspect_secrets(requirements: dict[str, tuple[str, ...]]) -> dict[str, Any]:
    """Return readiness and field names without returning any field values."""
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
        "region": _REGION or "AWS SDK default chain",
        "secretPrefix": _SECRET_PREFIX,
        "secrets": secrets,
        "configuredCount": sum(1 for item in secrets if item["configured"]),
        "requiredCount": len(secrets),
    }
