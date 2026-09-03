from __future__ import annotations

from pathlib import Path

import pytest

from plaud_plus_mcp.learn import remember, record_tool, snapshot_folders, status, suggest


def test_remember_and_suggest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ledger = tmp_path / "learn.jsonl"
    monkeypatch.setenv("PLAUD_PLUS_LEARN", str(ledger))
    snapshot_folders(
        [
            {"id": "fid-arp", "name": "ARP Anthracite Realty", "color": "#4c8eff"},
            {"id": "fid-gmw", "name": "GMW Greenmark", "color": "#46cf6c"},
        ],
        path=ledger,
    )
    record_tool(
        "mutate_recording",
        {"action": "move", "recording_id": "r1", "folder_id": "fid-arp", "new_name": "ARP site walk"},
        {"ok": True, "recording_id": "r1"},
        path=ledger,
    )
    record_tool(
        "edit_transcript",
        {"action": "rename_speaker", "recording_id": "r1", "original_label": "Speaker 1", "new_name": "Daniel Shanklin"},
        {"ok": True, "segments_updated": 4},
        path=ledger,
    )
    guess = suggest(title="ARP follow-up with the team", path=ledger)
    assert guess["do_not_apply"] is True
    assert guess["confidence"] == "UNVERIFIED"
    assert guess["folders"][0]["folder_id"] == "fid-arp"
    assert guess["speakers"][0]["new_name"] == "Daniel Shanklin"
    st = status(path=ledger)
    assert st["events"] >= 3
    remembered = remember("File Greenmark haul reviews in GMW Greenmark", path=ledger)
    assert remembered["stored"]["confidence"] == "UNVERIFIED"


def test_dry_run_correct_is_not_stored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ledger = tmp_path / "learn.jsonl"
    monkeypatch.setenv("PLAUD_PLUS_LEARN", str(ledger))
    record_tool(
        "edit_transcript",
        {"action": "correct", "find": "Entra", "replace": "Entra", "dry_run": True, "recording_id": "r"},
        {"ok": True, "dry_run": True, "matches": 1},
        path=ledger,
    )
    assert not ledger.exists()
    record_tool(
        "edit_transcript",
        {"action": "correct", "find": "Entra", "replace": "Azure AD", "dry_run": False, "recording_id": "r"},
        {"ok": True, "replacements": 1},
        path=ledger,
    )
    guess = suggest(path=ledger)
    assert guess["corrections"][0]["replace"] == "Azure AD"
