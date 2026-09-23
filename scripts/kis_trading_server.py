"""Start the upstream Trading MCP without leaking diagnostics into MCP stdio."""

import builtins
from pathlib import Path
import sys


# The upstream server is launched with its directory as cwd by kis_mcp.py.
sys.path.insert(0, str(Path.cwd()))

from tools import base  # noqa: E402


def diagnostic_print(*args, **kwargs):
    kwargs.setdefault("file", sys.stderr)
    builtins.print(*args, **kwargs)


# tools.base emits progress messages with print() while handling requests.
# stdout must contain only MCP JSON-RPC messages in stdio mode.
base.print = diagnostic_print

from server import main  # noqa: E402


if __name__ == "__main__":
    main()
