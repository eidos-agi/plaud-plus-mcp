from __future__ import annotations

import json

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


def test_train_help_exits_zero() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["train", "--help"])
    assert exc.value.code == 0


def test_learn_status_json(tmp_path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("PLAUD_PLUS_LEARN", str(tmp_path / "learn.jsonl"))
    assert main(["learn", "status"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True
    assert out["events"] == 0
    assert out["confidence"] == "UNVERIFIED"
    assert "illegal here" in out["note"]
