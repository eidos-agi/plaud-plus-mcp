from __future__ import annotations

import pytest

from plaud_plus_mcp.cli import main


def test_help_exits_zero() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0


def test_passthrough_to_plaud_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[list[str]] = []
    monkeypatch.setattr("plaud_plus_mcp.cli.ensure_session", lambda: "workspace_refresh")
    monkeypatch.setattr(
        "plaud_plus_mcp.cli.subprocess.call",
        lambda cmd: called.append(list(cmd)) or 0,
    )
    assert main(["folders"]) == 0
    assert called == [["plaud-tools", "folders"]]
