from __future__ import annotations

from plaud_plus_mcp.harness import (
    SYSTEM,
    _request_body,
    build_filing_messages,
    delta_from_chunk,
    iter_sse_data,
    parse_folder_suggestion,
    parse_note_suggestion,
)


def test_system_forbids_tools_and_filing() -> None:
    text = SYSTEM.format(folders="AIC Holdings, Personal")
    assert "cannot file" in text
    assert "tools" in text
    assert "FOLDER:" in text


def test_request_body_has_no_tools() -> None:
    body = _request_body(
        {"model": "deepseek-v4-flash", "url": "https://api.deepseek.com/v1/chat/completions", "key": "x"},
        [{"role": "user", "content": "hi"}],
        stream=True,
    )
    assert "tools" not in body
    assert body["stream"] is True
    assert "openrouter" not in body.get("model", "")
    assert body["thinking"] == {"type": "enabled"}


def test_parse_folder_suggestion_exact() -> None:
    folders = [
        {"id": "aic", "name": "AIC Holdings"},
        {"id": "per", "name": "Personal"},
    ]
    hit = parse_folder_suggestion("Host stand ops.\nFOLDER: AIC Holdings\nNOTE: restaurant comms", folders)
    assert hit == {"folder_id": "aic", "name": "AIC Holdings"}
    assert parse_note_suggestion("FOLDER: AIC Holdings\nNOTE: restaurant comms") == "restaurant comms"
    assert parse_folder_suggestion("FOLDER: NONE\nNOTE: skip", folders) is None
    assert parse_folder_suggestion("AIC Holdings", folders) == {"folder_id": "aic", "name": "AIC Holdings"}
    assert parse_folder_suggestion("**Folder:** Personal\n**Note:** family", folders) == {
        "folder_id": "per",
        "name": "Personal",
    }


def test_build_filing_messages_keeps_history() -> None:
    msgs = build_filing_messages(
        title="Host stand",
        when="Sat 11:17 PM",
        hour=23,
        mins=1,
        notes="",
        summary="privacy-safe inbox",
        transcript=None,
        folders=["AIC Holdings", "Personal"],
        history=[
            {"role": "user", "text": "which folder?"},
            {"role": "assistant", "text": "AIC Holdings\nFOLDER: AIC Holdings\nNOTE: host stand"},
        ],
        message="confirm",
    )
    assert msgs[0]["role"] == "system"
    assert msgs[-1]["content"] == "confirm"
    assert any(m["content"] == "which folder?" for m in msgs)


def test_iter_sse_and_delta() -> None:
    raw = [
        b"data: {\"choices\":[{\"delta\":{\"reasoning_content\":\"hmm\"}}]}\n",
        b"data: {\"choices\":[{\"delta\":{\"content\":\"AIC\"}}]}\n",
        b"data: [DONE]\n",
    ]
    chunks = list(iter_sse_data(iter(raw)))
    think, text = delta_from_chunk(chunks[0])
    assert think == "hmm"
    think, text = delta_from_chunk(chunks[1])
    assert text == "AIC"
