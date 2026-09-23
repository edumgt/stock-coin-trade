#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"

mkdir -p mcp
if [[ ! -d mcp/open-trading-api/.git ]]; then
  if [[ -e mcp/open-trading-api ]]; then
    echo "mcp/open-trading-api exists but is not a Git clone" >&2
    exit 1
  fi
  git clone --depth 1 --filter=blob:none https://github.com/koreainvestment/open-trading-api.git mcp/open-trading-api
fi

if [[ ! -x mcp/.venv/bin/uv ]]; then
  python3 -m venv mcp/.venv
  mcp/.venv/bin/python -m pip install 'uv>=0.8,<1'
fi

mcp/.venv/bin/uv sync --project 'mcp/open-trading-api/MCP/KIS Code Assistant MCP' --frozen
mcp/.venv/bin/uv sync --project 'mcp/open-trading-api/MCP/Kis Trading MCP'

python3 scripts/kis_mcp.py code --check
python3 scripts/kis_mcp.py trade --check
