from __future__ import annotations

import json
from pathlib import Path

from plaud_plus_mcp import harness, train
from plaud_plus_mcp.harness import complete_chat, llm_config, parse_chat_message
from plaud_plus_mcp.train import (
    append_chat,
    folder_buttons,
    load_chat,
    page_bundle,
    recording_view,
    tape_fields,
)


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
    page = page_bundle()
    assert "Plus train" in page
    assert 'e.key === "s"' in page
    assert "/api/label" in page
    assert "/api/skip" in page
    assert "/api/deepen" in page
    assert "/api/trash" in page
    assert "body_preview" in page or "blurb" in page
    assert "Full transcript" in page
    assert 'id="transcript"' in page
    assert "Trash" in page
    assert 'id="note"' in page
    assert "TEXTAREA" in page
    assert "/api/chat/stream" in page
    assert "Filing harness" in page
    assert "thinking" in page
    assert "desk" in page
    assert "cannot file" in page


def test_tape_fields_keeps_full_transcript() -> None:
    trans = ("Speaker: hello\n\n" * 2000)
    assert len(trans) > 8000
    fields = tape_fields("short summary", trans, utterances=12)
    assert fields["transcript"] == trans
    assert fields["transcript_chars"] == len(trans)
    assert fields["utterances"] == 12
    assert fields["deep"] is True
    assert len(fields["body_preview"]) <= 400


def test_chat_persists_to_disk(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PLAUD_PLUS_LEARN", str(tmp_path / "learn.jsonl"))
    append_chat("rec-1", {"role": "user", "text": "which folder?"})
    append_chat("rec-1", {"role": "assistant", "text": "Personal", "thinking": "late night family"})
    rows = load_chat("rec-1")
    assert len(rows) == 2
    assert rows[1]["text"] == "Personal"
    assert rows[1]["thinking"] == "late night family"
    assert (tmp_path / "chats" / "rec-1.jsonl").is_file()


def test_llm_config_uses_official_deepseek(monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-official")
    monkeypatch.setenv("OPENROUTER_API_KEY", "should-not-be-used")
    monkeypatch.setenv("DSH_HOME", "/tmp/not-a-real-dsh")
    cfg = llm_config()
    assert cfg is not None
    assert cfg["url"] == "https://api.deepseek.com/v1/chat/completions"
    assert cfg["model"] == "deepseek-v4-flash"
    assert "openrouter" not in cfg["url"]
    assert cfg["key"] == "sk-test-official"


def test_llm_config_ignores_openrouter_and_dsh(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-test")
    monkeypatch.setenv("DSH_HOME", str(tmp_path))
    (tmp_path / ".credentials.yaml").write_text('OPENROUTER_API_KEY: "leaked"\n')
    monkeypatch.setattr(harness, "deepseek_key", lambda: None)
    assert llm_config() is None


def test_parse_chat_prefers_reasoning_content() -> None:
    text, thinking = parse_chat_message(
        {
            "choices": [
                {
                    "message": {
                        "content": "AIC Holdings",
                        "reasoning_content": "host stand, not family",
                    }
                }
            ]
        }
    )
    assert text == "AIC Holdings"
    assert thinking == "host stand, not family"


def test_complete_chat_posts_to_official_api(monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-official")
    captured: dict = {}

    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": "Personal",
                                "reasoning_content": "late night family",
                            }
                        }
                    ]
                }
            ).encode()

    def fake_urlopen(req, timeout=0):
        captured["url"] = req.full_url
        captured["body"] = json.loads(req.data.decode())
        return FakeResp()

    monkeypatch.setattr(harness.urllib.request, "urlopen", fake_urlopen)
    text, thinking = complete_chat([{"role": "user", "content": "which folder?"}])
    assert captured["url"] == "https://api.deepseek.com/v1/chat/completions"
    assert captured["body"]["model"] == "deepseek-v4-flash"
    assert captured["body"]["thinking"] == {"type": "enabled"}
    assert "tools" not in captured["body"]
    assert "openrouter" not in captured["url"]
    assert text == "Personal"
    assert thinking == "late night family"


def test_train_source_has_no_openrouter_or_dsh() -> None:
    src = Path(train.__file__).read_text(encoding="utf-8") + Path(harness.__file__).read_text(encoding="utf-8")
    assert "OPENROUTER" not in src
    assert "openrouter.ai" not in src
    assert "DSH_HOME" not in src
    assert "eidos-harness-labs" not in src
