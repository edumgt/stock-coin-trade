"""AWS SSM Parameter Store credential source for the parallel ``*_aws`` test modules.

This is an independent track from ``broker_test.py``/``alpaca_test.py``/
``kb_token_test.py``, which keep reading ``kis.key``/``kb.key``/``al.key`` or
``KIS_*``/``KB_*``/``ALPACA_*`` environment variables unchanged. Modules in
this AWS track read the same kind of App Key/Secret/account values, but from
AWS Systems Manager Parameter Store (SecureString) instead of a file or plain
environment variable, so nothing sensitive needs to live on the EC2 disk or
in docker-compose.yml. Values are never logged or returned to the browser.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError, NoRegionError
except ImportError:  # boto3 is only required once this AWS track is actually used
    boto3 = None
    BotoCoreError = ClientError = NoRegionError = Exception


class AwsSecretError(RuntimeError):
    """A user-safe error that never includes secret values."""


_PARAM_PREFIX = os.environ.get("AWS_SSM_PARAMETER_PREFIX", "/stock-coin-trade").rstrip("/")
_REGION = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
_CACHE_TTL_SECONDS = 300

_client_lock = threading.Lock()
_client: Any = None
_cache: dict[str, dict[str, Any]] = {}
_cache_lock = threading.Lock()


def full_parameter_name(name: str) -> str:
    return f"{_PARAM_PREFIX}/{name.lstrip('/')}"


def _ssm_client():
    global _client
    if boto3 is None:
        raise AwsSecretError("boto3가 설치되지 않았습니다. requirements.txt의 boto3를 설치한 뒤 다시 시도하세요.")
    with _client_lock:
        if _client is None:
            _client = boto3.client("ssm", region_name=_REGION) if _REGION else boto3.client("ssm")
        return _client


def get_parameter(name: str, *, required: bool = True) -> str | None:
    """Fetch one SecureString parameter under ``AWS_SSM_PARAMETER_PREFIX``.

    ``name`` is the leaf path, e.g. ``kis/app_key`` becomes
    ``/stock-coin-trade/kis/app_key`` by default. Values are cached in
    memory for a short TTL to stay within SSM's request rate.
    """
    full_name = full_parameter_name(name)
    with _cache_lock:
        cached = _cache.get(full_name)
        if cached and cached["expires_at"] > time.time():
            return cached["value"]

    try:
        response = _ssm_client().get_parameter(Name=full_name, WithDecryption=True)
    except AwsSecretError:
        raise
    except NoRegionError as exc:
        raise AwsSecretError("AWS 리전이 설정되지 않았습니다. AWS_REGION을 설정하거나 리전이 있는 EC2 인스턴스 프로파일을 연결하세요.") from exc
    except (BotoCoreError, ClientError) as exc:
        error_code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
        if error_code == "ParameterNotFound":
            if required:
                raise AwsSecretError(f"SSM Parameter Store에 {full_name}이(가) 없습니다. 먼저 값을 생성하세요.") from exc
            return None
        raise AwsSecretError(f"AWS SSM Parameter Store 조회에 실패했습니다: {error_code or exc.__class__.__name__}") from exc

    value = response.get("Parameter", {}).get("Value")
    if not value:
        if required:
            raise AwsSecretError(f"SSM Parameter Store의 {full_name} 값이 비어 있습니다.")
        return None

    with _cache_lock:
        _cache[full_name] = {"value": value, "expires_at": time.time() + _CACHE_TTL_SECONDS}
    return value


def get_credentials(prefix: str, *, key_name: str = "app_key", secret_name: str = "secret") -> tuple[str, str]:
    """Fetch an App Key/Secret pair stored as ``{prefix}/{key_name}`` and ``{prefix}/{secret_name}``."""
    app_key = get_parameter(f"{prefix}/{key_name}")
    app_secret = get_parameter(f"{prefix}/{secret_name}")
    return app_key, app_secret


def inspect_parameters(names: list[str]) -> dict[str, Any]:
    """Return SSM readiness metadata without decrypting or exposing any value."""
    full_names = [full_parameter_name(name) for name in names]
    try:
        response = _ssm_client().get_parameters(Names=full_names, WithDecryption=False)
    except AwsSecretError:
        raise
    except NoRegionError as exc:
        raise AwsSecretError("AWS 리전이 설정되지 않았습니다. AWS_REGION을 설정하거나 리전이 있는 EC2 인스턴스 프로파일을 연결하세요.") from exc
    except (BotoCoreError, ClientError) as exc:
        code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
        raise AwsSecretError(f"AWS SSM Parameter Store 상태 조회에 실패했습니다: {code or exc.__class__.__name__}") from exc

    found = {item.get("Name"): item for item in response.get("Parameters", [])}
    parameters = []
    for full_name in full_names:
        item = found.get(full_name)
        parameters.append({
            "name": full_name,
            "configured": item is not None,
            "type": item.get("Type") if item else None,
            "tier": item.get("Tier") if item else None,
            "version": item.get("Version") if item else None,
            "lastModifiedAt": item.get("LastModifiedDate").isoformat() if item and item.get("LastModifiedDate") else None,
        })
    return {
        "region": _REGION or "AWS SDK default chain",
        "parameterPrefix": _PARAM_PREFIX,
        "parameters": parameters,
        "configuredCount": sum(1 for item in parameters if item["configured"]),
        "requiredCount": len(parameters),
    }
