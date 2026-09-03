from __future__ import annotations

from pathlib import Path

import pytest

from plaud_plus_mcp.learn import (
    cross_validate,
    fit,
    remember,
    record_tool,
    snapshot_filings,
    snapshot_folders,
    status,
    suggest,
)


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


def test_clock_title_and_probe_folder_do_not_match(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ledger = tmp_path / "learn.jsonl"
    monkeypatch.setenv("PLAUD_PLUS_LEARN", str(ledger))
    snapshot_folders(
        [
            {"id": "fid-probe", "name": "Plus Probe 2026-09-03"},
            {"id": "fid-arp", "name": "ARP Anthracite Realty"},
        ],
        path=ledger,
    )
    clock = suggest(title="2026-08-25 10:00:43", path=ledger)
    assert clock["clock_title"] is True
    assert clock["folders"] == []
    dated = suggest(title="09-03 Meeting: Centralized Tool Hub", path=ledger)
    assert dated["clock_title"] is False
    assert all(g["folder_id"] != "fid-probe" for g in dated["folders"])


def test_snapshot_filings_and_aliases(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ledger = tmp_path / "learn.jsonl"
    monkeypatch.setenv("PLAUD_PLUS_LEARN", str(ledger))
    snapshot_folders(
        [
            {"id": "fid-arp", "name": "ARP Anthracite Realty"},
            {"id": "fid-gmw", "name": "GMW Greenmark"},
        ],
        path=ledger,
    )
    snapshot_filings(
        [
            {
                "id": "r-filed",
                "title": "08-26 Optimizing Construction Pay Application Workflow with an AI Excel Plugin",
                "folder_id": "fid-arp",
            }
        ],
        path=ledger,
    )
    remember(
        "Pay apps and retainage go in ARP Anthracite Realty",
        extra={"folder_id": "fid-arp", "terms": ["pay application", "pay app", "retainage", "lender draw"]},
        path=ledger,
    )
    remember(
        "Cerebro / DD5 / Sage haul work goes in GMW Greenmark",
        extra={"folder_id": "fid-gmw", "terms": ["cerebro", "dd5", "sage", "fleet metrics"]},
        path=ledger,
    )
    pay = suggest(title="08-13 Refining the Pay Application and Lender Draw Process", path=ledger)
    assert pay["do_not_apply"] is True
    assert pay["folders"][0]["folder_id"] == "fid-arp"
    gmw = suggest(title="06-18 Meeting: Cerebro Metrics Dashboard", path=ledger)
    assert gmw["folders"][0]["folder_id"] == "fid-gmw"


def test_summary_body_beats_clock_and_blank_title(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ledger = tmp_path / "learn.jsonl"
    monkeypatch.setenv("PLAUD_PLUS_LEARN", str(ledger))
    snapshot_folders(
        [
            {"id": "fid-aic", "name": "AIC Holdings"},
            {"id": "fid-gmw", "name": "GMW Greenmark"},
            {"id": "fid-personal", "name": "Personal"},
        ],
        path=ledger,
    )
    remember(
        "AIC Hub / Entra / Paseo / Prim product work goes in AIC Holdings.",
        extra={"folder_id": "fid-aic", "terms": ["aic hub", "entra", "paseo", "prim"]},
        path=ledger,
    )
    remember(
        "Greenmark production is cerebro.greenmarkwaste.com",
        extra={"folder_id": "fid-gmw", "terms": ["cerebro.greenmarkwaste.com", "greenmarkwaste", "dd5"]},
        path=ledger,
    )
    remember(
        "Family / P-Paw / Sid go in Personal.",
        extra={"folder_id": "fid-personal", "terms": ["p-paw", "sid"]},
        path=ledger,
    )
    sidebar = suggest(
        title="Sidebar",
        body="The AIC Hub's Single Sign-On integration is being accelerated via Microsoft Entra.",
        path=ledger,
    )
    assert sidebar["folders"][0]["folder_id"] == "fid-aic"
    cerebro = suggest(
        title="Cerebro Metrics Dashboard",
        body="Confirmation that the production environment is at cerebro.greenmarkwaste.com.",
        path=ledger,
    )
    assert cerebro["folders"][0]["folder_id"] == "fid-gmw"
    clock = suggest(title="2026-08-25 10:00:43", body="Thank you.", path=ledger)
    assert clock["clock_title"] is True
    assert clock["folders"] == [] or clock["folders"][0]["folder_id"] != "fid-gmw"
    birthday = suggest(title="Coordination: P-Paw's 70th Birthday", path=ledger)
    assert birthday["folders"][0]["folder_id"] == "fid-personal"


def test_lift_model_learns_without_hand_aliases(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ledger = tmp_path / "learn.jsonl"
    monkeypatch.setenv("PLAUD_PLUS_LEARN", str(ledger))
    snapshot_folders(
        [
            {"id": "fid-aic", "name": "AIC Holdings"},
            {"id": "fid-arp", "name": "ARP Anthracite Realty"},
        ],
        path=ledger,
    )
    snapshot_filings(
        [
            {"id": "a1", "folder_id": "fid-aic", "title": "Paseo Engine High Availability and Failover"},
            {"id": "a2", "folder_id": "fid-aic", "title": "Prim board workers and plod cards"},
            {"id": "a3", "folder_id": "fid-aic", "title": "Palmwood AI budget for the team"},
            {
                "id": "r1",
                "folder_id": "fid-arp",
                "title": "Construction pay application G702 retainage",
                "body": "Clayton walked a GC pay app against the contract. Lender draw next.",
            },
            {
                "id": "r2",
                "folder_id": "fid-arp",
                "title": "Lender draw process with G703",
                "body": "Pay application retainage and lien waiver checks.",
            },
            {
                "id": "r3",
                "folder_id": "fid-arp",
                "title": "Excel plugin for pay apps",
                "body": "Claude Excel plugin generating G702 forms.",
            },
        ],
        path=ledger,
    )
    model = fit(ledger)
    aic_terms = set((model["folders"]["fid-aic"]["terms"] or {}))
    arp_terms = set((model["folders"]["fid-arp"]["terms"] or {}))
    assert "paseo" in aic_terms or "prim" in aic_terms
    assert any("pay" in t or "g702" in t or "retainage" in t for t in arp_terms)
    paseo = suggest(title="Paseo failover monitoring", path=ledger)
    assert paseo["do_not_apply"] is True
    assert paseo["folders"][0]["folder_id"] == "fid-aic"
    pay = suggest(title="G702 retainage on a pay application", path=ledger)
    assert pay["folders"][0]["folder_id"] == "fid-arp"
    cv = cross_validate(ledger)
    assert cv["n"] == 6
    assert cv["wrong"] <= 2


def test_hard_rule_build_vs_ops(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ledger = tmp_path / "learn.jsonl"
    monkeypatch.setenv("PLAUD_PLUS_LEARN", str(ledger))
    snapshot_folders(
        [
            {"id": "fid-aic", "name": "AIC Holdings"},
            {"id": "fid-arp", "name": "ARP Anthracite Realty"},
            {"id": "fid-gmw", "name": "GMW Greenmark"},
        ],
        path=ledger,
    )
    sheet = suggest(title="08-26 Meeting: Spreadsheet Process for Anthracite Realty Partners", path=ledger)
    assert sheet["do_not_apply"] is True
    assert sheet["folders"][0]["folder_id"] == "fid-aic"
    assert sheet["folders"][0].get("hard_rule")
    pay = suggest(title="G702 retainage on a pay application", path=ledger)
    assert pay["folders"][0]["folder_id"] == "fid-arp"
    paseo = suggest(title="Paseo Engine High Availability", path=ledger)
    assert paseo["folders"][0]["folder_id"] == "fid-aic"
    gmw = suggest(
        title="Cerebro Metrics Dashboard",
        body="Confirmation that the production environment is at cerebro.greenmarkwaste.com.",
        path=ledger,
    )
    assert gmw["folders"][0]["folder_id"] == "fid-gmw"
    clock = suggest(title="2026-08-25 10:00:43", path=ledger)
    assert clock["folders"] == []
