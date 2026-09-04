from __future__ import annotations

import json
from pathlib import Path

from plaud_plus_mcp import train
from plaud_plus_mcp.train import (
    PAGE,
    append_chat,
    complete_chat,
    folder_buttons,
    load_chat,
    parse_chat_message,
    recording_view,
    _llm_config,
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


def test_page_chat_heading_uses_model() -> None:
    assert "chat_model" in PAGE
    assert "on this recording" in PAGE


def test_llm_config_uses_official_deepseek(monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-official")
    monkeypatch.setenv("OPENROUTER_API_KEY", "should-not-be-used")
    monkeypatch.setenv("DSH_HOME", "/tmp/not-a-real-dsh")
    cfg = _llm_config()
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
    monkeypatch.setattr(train, "_deepseek_key", lambda: None)
    assert _llm_config() is None


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
        captured["timeout"] = timeout
        captured["body"] = json.loads(req.data.decode())
        captured["auth"] = req.get_header("Authorization")
        return FakeResp()

    monkeypatch.setattr(train.urllib.request, "urlopen", fake_urlopen)
    text, thinking = complete_chat([{"role": "user", "content": "which folder?"}])
    assert captured["url"] == "https://api.deepseek.com/v1/chat/completions"
    assert captured["body"]["model"] == "deepseek-v4-flash"
    assert captured["body"]["thinking"] == {"type": "enabled"}
    assert captured["body"]["reasoning_effort"] == "high"
    assert "openrouter" not in captured["url"]
    assert text == "Personal"
    assert thinking == "late night family"


def test_train_source_has_no_openrouter_or_dsh() -> None:
    src = Path(train.__file__).read_text(encoding="utf-8")
    assert "OPENROUTER" not in src
    assert "openrouter.ai" not in src
    assert "DSH_HOME" not in src
    assert "eidos-harness-labs" not in src
