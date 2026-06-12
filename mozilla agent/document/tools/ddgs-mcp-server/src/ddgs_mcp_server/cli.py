"""Launch the pinned DDGS MCP server for mcpd."""

from __future__ import annotations

import os
import sys


def main() -> None:
    """Forward execution to the bundled DDGS MCP entrypoint."""
    os.execv(
        sys.executable,
        [sys.executable, "-m", "ddgs.cli", "mcp", *sys.argv[1:]],
    )
