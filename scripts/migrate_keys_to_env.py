"""Migrate legacy local key files into the repository-root .env without printing values."""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"


def assignments(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        values[name.strip().lower().replace("-", "_")] = value.strip().strip('"').strip("'")
    return values


def first(values: dict[str, str], *names: str) -> str:
    return next((values[name] for name in names if values.get(name)), "")


def collect() -> tuple[dict[str, str], list[Path]]:
    sources = [
        ROOT / "kis.key", ROOT / "kb.key", ROOT / "kb2.key", ROOT / "al.key",
        ROOT / "alpaca-re.key", ROOT / "s3-user_accessKeys.key", ROOT / "mcp" / "kis-trade-mcp.env",
    ]
    kis, kb, kb2, alpaca = (assignments(path) for path in sources[:4])
    mcp = assignments(sources[-1])
    values = {
        "KIS_PAPER_APP_KEY": first(kis, "app_key", "appkey") or first(mcp, "kis_paper_app_key"),
        "KIS_PAPER_APP_SECRET": first(kis, "secret", "app_secret", "appsecret") or first(mcp, "kis_paper_app_secret"),
        "KIS_PAPER_ACCOUNT_NO": first(kis, "account", "account_no", "cano"),
        "KB_APP_KEY": first(kb, "appkey", "app_key"),
        "KB_APP_SECRET": first(kb, "secret", "appsecret", "app_secret"),
        "KB_SECONDARY_APP_KEY": first(kb2, "appkey", "app_key"),
        "KB_SECONDARY_APP_SECRET": first(kb2, "secret", "appsecret", "app_secret"),
        "ALPACA_API_KEY": first(alpaca, "key", "api_key", "alpaca_api_key"),
        "ALPACA_SECRET_KEY": first(alpaca, "secret", "secret_key", "alpaca_secret_key"),
    }

    reference = sources[4]
    if reference.is_file():
        values["ALPACA_REFERENCE_KEY"] = next((line.strip() for line in reference.read_text(encoding="utf-8-sig").splitlines() if line.strip()), "")

    aws_csv = sources[5]
    if aws_csv.is_file():
        rows = list(csv.reader(aws_csv.read_text(encoding="utf-8-sig").splitlines()))
        credential = next((row for row in rows if len(row) >= 2 and row[0].strip().upper().startswith(("AKIA", "ASIA"))), None)
        if credential:
            values["AWS_ACCESS_KEY_ID"] = credential[0].strip()
            values["AWS_SECRET_ACCESS_KEY"] = credential[1].strip()
    return {name: value for name, value in values.items() if value}, sources


def current_values(lines: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in lines:
        if "=" not in line or line.lstrip().startswith("#"):
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        if name:
            result[name] = value.strip()
    return result


def merge_env(values: dict[str, str]) -> list[str]:
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines() if ENV_PATH.is_file() else []
    existing = current_values(lines)
    pending = {name: value for name, value in values.items() if not existing.get(name)}
    replaced: set[str] = set()
    output: list[str] = []
    for line in lines:
        if "=" in line and not line.lstrip().startswith("#"):
            name = line.split("=", 1)[0].strip()
            if name in pending:
                output.append(f"{name}={json.dumps(pending[name], ensure_ascii=False)}")
                replaced.add(name)
                continue
        output.append(line)
    additions = [name for name in pending if name not in replaced]
    if additions:
        output.extend(["", "# Migrated broker/cloud credentials (legacy key files removed)"])
        output.extend(f"{name}={json.dumps(pending[name], ensure_ascii=False)}" for name in additions)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--delete-source", action="store_true")
    args = parser.parse_args()
    values, sources = collect()
    print("variables=" + ",".join(sorted(values)))
    print("source_files=" + ",".join(path.relative_to(ROOT).as_posix() for path in sources if path.is_file()))
    if not args.apply:
        print("preview only; add --apply to update .env")
        return 0
    if not values:
        raise SystemExit("No legacy credentials were found.")
    output = merge_env(values)
    temporary = ENV_PATH.with_name(".env.migrating")
    temporary.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")
    temporary.chmod(0o600)
    os.replace(temporary, ENV_PATH)
    ENV_PATH.chmod(0o600)
    print(f"updated={ENV_PATH.name} mode=600")
    if args.delete_source:
        for path in sources:
            if path.is_file():
                path.unlink()
                print(f"deleted={path.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
