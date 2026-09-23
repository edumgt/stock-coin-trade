"""Launch the official KIS MCP servers from this workspace."""

from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import sys


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "mcp" / "open-trading-api" / "MCP"
SERVERS = {
    "code": (SOURCE / "KIS Code Assistant MCP", ["run", "server.py", "--stdio"]),
    "trade": (SOURCE / "Kis Trading MCP", ["run", "python", "server.py"]),
}


def read_values(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"\'')
    return values


def trade_environment() -> dict[str, str]:
    local = read_values(ROOT / "kis.key")
    dotenv = read_values(ROOT / ".env")
    if (os.environ.get("KIS_ENVIRONMENT") or dotenv.get("KIS_ENVIRONMENT") or "paper") != "paper":
        raise ValueError("KIS_ENVIRONMENT must be paper for the MCP trading server")

    def pick(*names: str) -> str:
        for name in names:
            value = os.environ.get(name) or dotenv.get(name) or local.get(name)
            if value:
                return value
        return ""

    paper_key, paper_secret = pick("KIS_PAPER_APP_KEY"), pick("KIS_PAPER_APP_SECRET")
    legacy_key, legacy_secret = pick("KIS_APP_KEY"), pick("KIS_APP_SECRET")
    if bool(paper_key) != bool(paper_secret):
        raise ValueError("KIS_PAPER_APP_KEY and KIS_PAPER_APP_SECRET must both be set")
    if paper_key:
        key, secret = paper_key, paper_secret
    elif legacy_key and legacy_secret:
        key, secret = legacy_key, legacy_secret
    else:
        key = local.get("App-KEY") or local.get("app_key", "")
        secret = local.get("Secret") or local.get("secret", "")
    account = pick("KIS_PAPER_ACCOUNT_NO", "KIS_ACCOUNT_NO", "account")
    if not key or not secret:
        raise ValueError("KIS paper credentials are missing from .env or kis.key")
    if not re.fullmatch(r"\d{8}-\d{2}", account):
        raise ValueError("KIS paper account must have the form 12345678-01")

    # The trading server can place orders. Never forward live credentials.
    env = {name: value for name, value in os.environ.items() if not name.startswith("KIS_")}
    env.update(
        ENV="live",  # Upstream transport configuration filename, not live trading.
        MCP_TYPE="stdio",
        KIS_APP_KEY="",
        KIS_APP_SECRET="",
        KIS_ACCT_STOCK="",
        KIS_ACCT_FUTURE="",
        KIS_PAPER_APP_KEY=key,
        KIS_PAPER_APP_SECRET=secret,
        KIS_PAPER_STOCK=account[:8],
        KIS_PROD_TYPE=account[-2:],
        KIS_HTS_ID=pick("KIS_HTS_ID"),
    )
    # Upstream writes kis_devlp.yaml under HOME. Keep it inside gitignored mcp/.
    private_home = ROOT / "mcp" / "home"
    private_home.mkdir(parents=True, exist_ok=True, mode=0o700)
    private_home.chmod(0o700)
    env["HOME"] = str(private_home)
    return env


def main() -> int:
    if len(sys.argv) not in (2, 3) or sys.argv[1] not in SERVERS or (len(sys.argv) == 3 and sys.argv[2] != "--check"):
        print("usage: python3 scripts/kis_mcp.py {code|trade} [--check]", file=sys.stderr)
        return 2

    kind = sys.argv[1]
    directory, args = SERVERS[kind]
    uv = ROOT / "mcp" / ".venv" / "bin" / "uv"
    executable = str(uv) if uv.is_file() else shutil.which("uv")
    if not directory.is_dir():
        print("KIS MCP source is missing; see README.md > KIS MCP", file=sys.stderr)
        return 1
    if not executable:
        print("uv is missing; see README.md > KIS MCP", file=sys.stderr)
        return 1
    try:
        env = trade_environment() if kind == "trade" else os.environ.copy()
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if len(sys.argv) == 3:
        print(f"{kind} MCP configuration is ready")
        return 0
    os.chdir(directory)
    os.execvpe(executable, [executable, *args], env)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
