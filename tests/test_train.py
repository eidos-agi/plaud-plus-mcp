from __future__ import annotations

from plaud_plus_mcp.train import PAGE, append_chat, folder_buttons, load_chat, recording_view


def test_folder_buttons_hide_probe() -> None:
    buttons = folder_buttons(
        [
            {"id": "aic", "name": "AIC Holdings", "color": "#191919"},
            {"id": "probe", "name": "Plus Probe 2026-09-03", "color": "#ff8a3d"},
            {"id": "gmw", "name": "GMW Greenmark", "color": "#46cf6c"},
        ]
    )
    ids = [b["id"] for b in buttons]
    assert ids == ["aic", "gmw"]


def test_recording_view_extracts_people_and_place() -> None:
    view = recording_view(
        {
            "id": "r1",
            "title": "P-Paw's 70th Birthday in Texas",
            "date": "2026-08-01T11:38",
            "duration_minutes": 1,
        },
        "Wyatt and Colleen. Send Angela a text.",
        11,
    )
    assert view["id"] == "r1"
    assert "p-paw" in view["people"]
    assert "texas" in view["places"]


def test_page_has_yes_and_skip_keys() -> None:
    assert "Plus train" in PAGE
    assert 'e.key === "s"' in PAGE
    assert "/api/label" in PAGE
    assert "/api/skip" in PAGE
    assert "/api/deepen" in PAGE
    assert "/api/trash" in PAGE
    assert "body_preview" in PAGE or "blurb" in PAGE
    assert "Dive deeper" in PAGE
    assert "Trash" in PAGE
    assert 'id="note"' in PAGE
    assert "TEXTAREA" in PAGE
    assert "/api/chat" in PAGE
    assert "DeepSeek" in PAGE
    assert "thinking" in PAGE


def test_chat_persists_to_disk(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PLAUD_PLUS_LEARN", str(tmp_path / "learn.jsonl"))
    append_chat("rec-1", {"role": "user", "text": "which folder?"})
    append_chat("rec-1", {"role": "assistant", "text": "Personal", "thinking": "late night family"})
    rows = load_chat("rec-1")
    assert len(rows) == 2
    assert rows[1]["text"] == "Personal"
    assert rows[1]["thinking"] == "late night family"
    assert (tmp_path / "chats" / "rec-1.jsonl").is_file()