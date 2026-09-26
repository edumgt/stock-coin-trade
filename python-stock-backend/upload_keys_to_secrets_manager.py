"""Create real AWS Secrets Manager secrets from this repository's broker keys.

Preview is the default and never prints values. Use ``--apply`` to create:
``stock-coin-trade/kis``, ``stock-coin-trade/kb`` and
``stock-coin-trade/alpaca`` as JSON secrets.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import boto3
from botocore.exceptions import BotoCoreError, ClientError, NoRegionError


KEY_DIRS = (Path("/run/secrets"), Path("/app"), Path.cwd())
DEFAULT_PREFIX = os.getenv("AWS_SECRETS_MANAGER_PREFIX", "stock-coin-trade").strip("/")
DEFAULT_REGION = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")


def read_key_file(filename: str) -> dict[str, str]:
    path = next((directory / filename for directory in KEY_DIRS if (directory / filename).is_file()), None)
    if path is None:
        return {}
    values = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        values[name.strip().lower().replace("-", "_")] = value.strip().strip('"').strip("'")
    return values


def first_value(*values: str | None) -> str | None:
    return next((value.strip() for value in values if value and value.strip()), None)


def file_value(values: dict[str, str], *names: str) -> str | None:
    return first_value(*(values.get(name) for name in names))


def collect_secrets() -> dict[str, dict[str, str | None]]:
    kis, kb, alpaca = read_key_file("kis.key"), read_key_file("kb.key"), read_key_file("al.key")
    return {
        "kis": {
            "app_key": first_value(os.getenv("KIS_PAPER_APP_KEY"), os.getenv("KIS_APP_KEY"), file_value(kis, "app_key", "appkey")),
            "secret": first_value(os.getenv("KIS_PAPER_APP_SECRET"), os.getenv("KIS_APP_SECRET"), file_value(kis, "secret", "app_secret", "appsecret")),
            "account": first_value(os.getenv("KIS_PAPER_ACCOUNT_NO"), os.getenv("KIS_ACCOUNT_NO"), file_value(kis, "account", "account_no")),
        },
        "kb": {
            "app_key": first_value(os.getenv("KB_APP_KEY"), file_value(kb, "appkey", "app_key")),
            "secret": first_value(os.getenv("KB_APP_SECRET"), file_value(kb, "secret", "appsecret", "app_secret")),
        },
        "alpaca": {
            "api_key": first_value(os.getenv("ALPACA_API_KEY"), file_value(alpaca, "key", "api_key", "alpaca_api_key", "apca_api_key_id")),
            "secret_key": first_value(os.getenv("ALPACA_SECRET_KEY"), file_value(alpaca, "secret", "secret_key", "alpaca_secret_key", "apca_api_secret_key")),
        },
    }


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="create secrets (default: preview only)")
    parser.add_argument("--overwrite", action="store_true", help="create a new version when a secret exists")
    parser.add_argument("--prefix", default=DEFAULT_PREFIX)
    parser.add_argument("--region", default=DEFAULT_REGION)
    parser.add_argument("--profile", help="local AWS CLI profile; omit on EC2")
    parser.add_argument("--kms-key-id", default=os.getenv("AWS_SECRETS_MANAGER_KMS_KEY_ID"))
    parser.add_argument("--only", choices=("kis", "kb", "alpaca"))
    return parser.parse_args()


def main():
    args = parse_args()
    if not args.region:
        raise SystemExit("AWS_REGION 또는 --region이 필요합니다.")
    prefix = args.prefix.strip("/")
    secrets = collect_secrets()
    if args.only:
        secrets = {args.only: secrets[args.only]}
    missing = [f"{service}.{field}" for service, document in secrets.items() for field, value in document.items() if not value]
    print(f"region={args.region} prefix={prefix} mode={'APPLY' if args.apply else 'PREVIEW'}")
    for service, document in secrets.items():
        state = "READY" if all(document.values()) else "MISSING"
        print(f"{state} {prefix}/{service} fields={','.join(document)}")
    if missing:
        raise SystemExit("필수 값을 찾지 못했습니다: " + ", ".join(missing))
    if not args.apply:
        print("미리보기 완료. 실제 생성은 --apply를 추가하세요.")
        return

    try:
        session = boto3.Session(profile_name=args.profile, region_name=args.region)
        identity = session.client("sts").get_caller_identity()
        print(f"AWS account={identity.get('Account')} caller={identity.get('Arn')}")
        client = session.client("secretsmanager")
        for service, document in secrets.items():
            name = f"{prefix}/{service}"
            payload = json.dumps(document, ensure_ascii=False, separators=(",", ":"))
            request = {
                "Name": name,
                "Description": f"stock-coin-trade {service} credentials",
                "SecretString": payload,
                "Tags": [
                    {"Key": "Application", "Value": "stock-coin-trade"},
                    {"Key": "ManagedBy", "Value": "upload_keys_to_secrets_manager.py"},
                ],
            }
            if args.kms_key_id:
                request["KmsKeyId"] = args.kms_key_id
            try:
                response = client.create_secret(**request)
                print(f"CREATED {name} arn={response.get('ARN')}")
            except ClientError as exc:
                if exc.response.get("Error", {}).get("Code") != "ResourceExistsException" or not args.overwrite:
                    raise
                update = {"SecretId": name, "Description": request["Description"], "SecretString": payload}
                if args.kms_key_id:
                    update["KmsKeyId"] = args.kms_key_id
                response = client.update_secret(**update)
                print(f"UPDATED {name} version={response.get('VersionId')}")
    except NoRegionError as exc:
        raise SystemExit("AWS 리전을 확인하세요.") from exc
    except (BotoCoreError, ClientError) as exc:
        code = getattr(exc, "response", {}).get("Error", {}).get("Code", exc.__class__.__name__)
        raise SystemExit(f"Secrets Manager 작업 실패: {code} (IAM·리전·중복 여부를 확인하세요.)") from exc
    print("완료. Secrets Manager 콘솔에서 3개 보안 암호 이름을 확인하세요.")


if __name__ == "__main__":
    main()
