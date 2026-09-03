"""MCP stdio: plaud-tools tools + one learn facade."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any

import mcp.server.stdio
import mcp.types as types
from mcp.server.lowlevel import Server
from plaud_tools.core.client import PlaudClient
from plaud_tools.core.session import SessionManager, SessionStore
from plaud_tools.mcp_pt.mcp import build_handlers
from plaud_tools.mcp_pt.server import _TOOLS

from . import __version__
from .auth import AuthError, ensure_session
from .learn import recall, record_tool, remember, snapshot_folders, status, suggest

LEARN_TOOL = types.Tool(
    name="plaud_plus_learn",
    description=(
        "Local observations from this machine's Plaud Plus writes. "
        "action=status|recall|suggest|remember|snapshot. Suggestions are UNVERIFIED; "
        "never apply them without asking the human. Not lessons.md CONFIRMED."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["status", "recall", "suggest", "remember", "snapshot"],
            },
            "title": {"type": "string", "description": "For suggest: recording title"},
            "recording_id": {"type": "string", "description": "For suggest"},
            "claim": {"type": "string", "description": "For remember: a short observation"},
            "kind": {"type": "string", "description": "For recall: move|folder|rename_speaker|correct|note"},
            "limit": {"type": "integer", "minimum": 1, "default": 20},
        },
        "required": ["action"],
    },
    annotations=types.ToolAnnotations(
        title="Plaud Plus learn (local, unverified)",
        read_only_hint=False,
        open_world_hint=False,
    ),
)


def _json_tool(payload: dict[str, Any], is_error: bool = False) -> dict[str, Any]:
    result: dict[str, Any] = {
        "content": [{"type": "text", "text": json.dumps(payload, separators=(",", ":"), ensure_ascii=False)}]
    }
    if is_error:
        result["isError"] = True
    return result


def _folders_from_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for key in ("folders", "items", "data"):
            val = payload.get(key)
            if isinstance(val, list):
                return [x for x in val if isinstance(x, dict)]
    return []


def _wrap_handler(name: str, handler: Any) -> Any:
    def wrapped(**kwargs: Any) -> dict[str, Any]:
        result = handler(**kwargs)
        if not result.get("isError"):
            try:
                payload = json.loads(result["content"][0]["text"])
            except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                payload = {}
            if isinstance(payload, dict):
                record_tool(name, kwargs, payload)
        return result

    return wrapped


def _learn_handler(get_client: Any, get_folders: Any) -> Any:
    def plaud_plus_learn(
        action: str,
        title: str | None = None,
        recording_id: str | None = None,
        claim: str | None = None,
        kind: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        if action == "status":
            return _json_tool(status())
        if action == "recall":
            return _json_tool(recall(kind=kind, limit=limit))
        if action == "remember":
            if not claim:
                return _json_tool(
                    {"error": "claim is required for remember", "error_code": "validation", "retryable": False},
                    is_error=True,
                )
            return _json_tool(remember(claim))
        if action == "snapshot":
            try:
                result = get_folders()
                payload = json.loads(result["content"][0]["text"])
                n = snapshot_folders(_folders_from_list(payload))
            except Exception as exc:
                return _json_tool(
                    {"error": f"snapshot failed: {exc}", "error_code": "api_error", "retryable": True},
                    is_error=True,
                )
            return _json_tool({"ok": True, "ingested": n, **status()})
        if action == "suggest":
            hint_title = title
            if recording_id and not hint_title:
                client = get_client()
                if client is not None:
                    try:
                        detail = client.get_recording(recording_id)
                        hint_title = getattr(detail, "filename", None) or hint_title
                    except Exception:
                        pass
            return _json_tool(suggest(title=hint_title, recording_id=recording_id))
        return _json_tool(
            {"error": f"unknown action {action!r}", "error_code": "validation", "retryable": False},
            is_error=True,
        )

    return plaud_plus_learn


def _maybe_snapshot(handlers: dict[str, Any]) -> None:
    lister = handlers.get("list_folders")
    if lister is None:
        return
    try:
        result = lister()
        payload = json.loads(result["content"][0]["text"])
        snapshot_folders(_folders_from_list(payload))
    except Exception:
        return


def _make_server() -> Server:
    store = SessionStore()
    manager = SessionManager(store)

    def get_client() -> PlaudClient | None:
        if store.load() is None:
            return None
        return PlaudClient(manager)

    handlers = {name: _wrap_handler(name, fn) for name, fn in build_handlers(get_client).items()}
    handlers["plaud_plus_learn"] = _learn_handler(get_client, handlers["list_folders"])
    _maybe_snapshot(handlers)

    async def list_tools(_ctx: Any, _params: Any) -> types.ListToolsResult:
        return types.ListToolsResult(tools=[*_TOOLS, LEARN_TOOL])

    async def call_tool(_ctx: Any, params: types.CallToolRequestParams) -> types.CallToolResult:
        name = params.name
        arguments = params.arguments or {}
        handler = handlers.get(name)
        if handler is None:
            payload = {"error": f"Unknown tool: {name}"}
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=json.dumps(payload, separators=(",", ":")))],
                is_error=True,
            )
        try:
            result = await asyncio.to_thread(handler, **arguments)
            text = result["content"][0]["text"]
            is_error = bool(result.get("isError"))
        except TypeError as exc:
            payload = {
                "error": f"Invalid arguments for tool '{name}': {exc}",
                "error_code": "validation",
                "retryable": False,
            }
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=json.dumps(payload, separators=(",", ":")))],
                is_error=True,
            )
        except ValueError as exc:
            payload = {"error": str(exc), "error_code": "validation", "retryable": False}
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=json.dumps(payload, separators=(",", ":")))],
                is_error=True,
            )
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=text)],
            is_error=is_error,
        )

    return Server("plaud-plus-mcp", version=__version__, on_list_tools=list_tools, on_call_tool=call_tool)


async def _run() -> None:
    server = _make_server()
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main() -> None:
    parser = argparse.ArgumentParser(prog="plaud-plus-mcp")
    parser.add_argument("--version", action="version", version=f"plaud-plus-mcp {__version__}")
    parser.parse_args()
    try:
        source = ensure_session()
    except AuthError as exc:
        print(f"plaud-plus-mcp: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    except Exception as exc:
        print(f"plaud-plus-mcp: auth failed: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    print(f"plaud-plus-mcp: session via {source}", file=sys.stderr)
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        print(f"plaud-plus-mcp: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
