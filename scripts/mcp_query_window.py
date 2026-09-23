"""Local browser console for the official KIS MCP servers.

Run with the Code Assistant MCP virtual environment's Python interpreter:
  mcp/open-trading-api/MCP/KIS Code Assistant MCP/.venv/bin/python scripts/mcp_query_window.py
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import sys
import webbrowser

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


ROOT = Path(__file__).resolve().parents[1]
PAGE = Path(__file__).with_suffix(".html")
MAX_BODY = 64 * 1024


async def query_mcp(server: str, tool_name: str | None, arguments: dict) -> dict:
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(ROOT / "scripts" / "kis_mcp.py"), server],
        cwd=ROOT,
    )
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            if tool_name is None:
                listing = await session.list_tools()
                return {"tools": [
                    {
                        "name": tool.name,
                        "title": tool.title or tool.name,
                        "description": tool.description or "",
                        "inputSchema": tool.inputSchema,
                    }
                    for tool in listing.tools
                ]}
            # Refuse names that are not advertised by the selected server.
            listing = await session.list_tools()
            if tool_name not in {tool.name for tool in listing.tools}:
                raise ValueError("선택한 MCP 서버에 없는 도구입니다.")
            result = await session.call_tool(
                tool_name,
                arguments,
                read_timeout_seconds=timedelta(seconds=90),
            )
            return {"result": result.model_dump(mode="json")}


class ConsoleHandler(BaseHTTPRequestHandler):
    server: "ConsoleServer"

    def log_message(self, format: str, *args: object) -> None:
        # Never log request bodies or MCP results.
        pass

    def _same_origin(self) -> bool:
        expected = f"127.0.0.1:{self.server.server_port}"
        return self.headers.get("Host") == expected and self.headers.get("Origin", f"http://{expected}") == f"http://{expected}"

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if not self._same_origin():
            self.send_error(403)
            return
        if self.path != "/":
            self.send_error(404)
            return
        body = PAGE.read_text(encoding="utf-8").replace("__CONSOLE_TOKEN__", self.server.token).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        if not self._same_origin() or self.headers.get("X-MCP-Console-Token") != self.server.token:
            self._json(403, {"error": "이 창에서 보낸 요청만 허용됩니다."})
            return
        if self.path not in ("/api/tools", "/api/call") or self.headers.get("Content-Type", "").split(";", 1)[0] != "application/json":
            self._json(404, {"error": "지원하지 않는 요청입니다."})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= MAX_BODY:
                raise ValueError("요청 크기가 올바르지 않습니다.")
            payload = json.loads(self.rfile.read(size))
            if not isinstance(payload, dict) or payload.get("server") not in ("code", "trade"):
                raise ValueError("MCP 서버를 선택하세요.")
            tool = None
            arguments = {}
            if self.path == "/api/call":
                tool = payload.get("tool")
                arguments = payload.get("arguments")
                if not isinstance(tool, str) or not tool or not isinstance(arguments, dict):
                    raise ValueError("도구와 JSON 객체 인자를 입력하세요.")
                if payload["server"] == "trade" and payload.get("confirm_trade") is not True:
                    raise ValueError("거래 MCP 도구 실행을 확인해야 합니다.")
            result = asyncio.run(asyncio.wait_for(query_mcp(payload["server"], tool, arguments), timeout=120))
            self._json(200, result)
        except (ValueError, json.JSONDecodeError) as exc:
            self._json(400, {"error": str(exc)})
        except TimeoutError:
            self._json(504, {"error": "MCP 서버 응답 시간이 초과됐습니다."})
        except Exception as exc:
            # MCP/stdio failures may include secret-bearing upstream messages.
            print(f"MCP 요청 실패: {type(exc).__name__}", file=sys.stderr)
            self._json(502, {"error": "MCP 서버 요청에 실패했습니다. 설치 상태와 터미널 오류를 확인하세요."})


class ConsoleServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, port: int):
        super().__init__(("127.0.0.1", port), ConsoleHandler)
        self.token = secrets.token_urlsafe(32)


def main() -> None:
    parser = argparse.ArgumentParser(description="로컬 KIS MCP 질의 창")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    with ConsoleServer(args.port) as server:
        url = f"http://127.0.0.1:{server.server_port}/"
        print(f"KIS MCP 질의 창: {url}")
        print("종료: Ctrl+C")
        if not args.no_browser:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
