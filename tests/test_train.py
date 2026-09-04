from __future__ import annotations

from plaud_plus_mcp.train import folder_buttons, recording_view, PAGE


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
    assert "body_preview" in PAGE or "blurb" in PAGE