"""MCP stdio entry: refresh auth, then run plaud-tools' server."""

from __future__ import annotations

import sys

from .auth import AuthError, ensure_session


def main() -> None:
    if "--version" in sys.argv:
        from plaud_tools.mcp_pt.server import main as plaud_mcp_main

        plaud_mcp_main()
        return
    try:
        source = ensure_session()
    except AuthError as exc:
        print(f"plaud-plus-mcp: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    except Exception as exc:
        print(f"plaud-plus-mcp: auth failed: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    print(f"plaud-plus-mcp: session via {source}", file=sys.stderr)
    from plaud_tools.mcp_pt.server import main as plaud_mcp_main

    plaud_mcp_main()


if __name__ == "__main__":
    main()
