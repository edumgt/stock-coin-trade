"""Create real AWS Secrets Manager secrets from ``.env`` broker credentials.

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
from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
DEFAULT_PREFIX = os.getenv("AWS_SECRETS_MANAGER_PREFIX", "stock-coin-trade").strip("/")
DEFAULT_REGION = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")


def first_value(*values: str | None) -> str | None:
    return next((value.strip() for value in values if value and value.strip()), None)


def collect_secrets() -> dict[str, dict[str, str | None]]:
    return {
        "kis": {
            "app_key": first_value(os.getenv("KIS_PAPER_APP_KEY")),
            "secret": first_value(os.getenv("KIS_PAPER_APP_SECRET")),
            "account": first_value(os.getenv("KIS_PAPER_ACCOUNT_NO")),
        },
        "kb": {
            "app_key": first_value(os.getenv("KB_APP_KEY")),
            "secret": first_value(os.getenv("KB_APP_SECRET")),
        },
        "alpaca": {
            "api_key": first_value(os.getenv("ALPACA_API_KEY")),
            "secret_key": first_value(os.getenv("ALPACA_SECRET_KEY")),
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
