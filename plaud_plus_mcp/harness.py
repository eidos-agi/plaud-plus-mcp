"""Filing harness for one Plaud recording.

Official DeepSeek only. No tools, no coding agent, no OpenRouter, no DSH.
Cannot file, trash, or skip — the human clicks.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any, Iterator

DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-v4-flash"
KR_LLM_ACCOUNT = "deepseek"

SYSTEM = (
    "You are the Plus filing harness. One Plaud recording. "
    "You cannot file, trash, skip, or call tools. "
    "A person is not a folder — decide from who / where / when. "
    "Do not invent tenants from a clock title. "
    "Folders: {folders}. "
    "Reply in a few short sentences, then end with exactly two lines:\n"
    "FOLDER: <one folder name from the list, or NONE>\n"
    "NOTE: <one trainer note Daniel could type>"
)

FOLDER_LINE = re.compile(r"(?im)^\*{0,2}\s*FOLDER:\s*\*{0,2}\s*(.+?)\s*$")
NOTE_LINE = re.compile(r"(?im)^\*{0,2}\s*NOTE:\s*\*{0,2}\s*(.+?)\s*$")


def deepseek_key() -> str | None:
    """Official DeepSeek key only. Never logs the secret."""
    env = (os.environ.get("DEEPSEEK_API_KEY") or "").strip()
    if env:
        return env
    try:
        import keyring

        stored = keyring.get_password("plaud-plus", KR_LLM_ACCOUNT)
    except Exception:
        return None
    stored = (stored or "").strip()
    return stored or None


def llm_config() -> dict[str, str] | None:
    key = deepseek_key()
    if not key:
        return None
    return {
        "url": DEEPSEEK_URL,
        "model": os.environ.get("PLAUD_PLUS_LLM_MODEL") or DEEPSEEK_MODEL,
        "key": key,
        "name": "DeepSeek",
    }


def no_key_message() -> str:
    return (
        "No DeepSeek key. Set DEEPSEEK_API_KEY or store it in the "
        "plaud-plus keychain (account deepseek). Not OpenRouter, not a coding agent."
    )


def parse_chat_message(data: dict[str, Any]) -> tuple[str, str]:
    try:
        msg = data["choices"][0]["message"]
    except (KeyError, IndexError, TypeError):
        return "DeepSeek returned an empty reply.", ""
    text = str(msg.get("content") or "").strip()
    thinking = str(msg.get("reasoning_content") or msg.get("reasoning") or "").strip()
    if not text and thinking:
        text = thinking.split("\n\n")[-1].strip()
    return text or "DeepSeek returned an empty reply.", thinking


def parse_folder_suggestion(text: str, folders: list[dict[str, Any]]) -> dict[str, str] | None:
    if not text or not folders:
        return None
    match = FOLDER_LINE.search(text)
    raw = (match.group(1) if match else "").strip()
    if raw.upper() == "NONE":
        return None
    named = [f for f in folders if str(f.get("name") or "").strip()]
    if raw:
        key = raw.lower()
        exact = [f for f in named if str(f["name"]).lower() == key]
        if len(exact) == 1:
            hit = exact[0]
            return {"folder_id": str(hit["id"]), "name": str(hit["name"])}
        contained = [
            f
            for f in named
            if key in str(f["name"]).lower() or str(f["name"]).lower() in key
        ]
        if len(contained) == 1:
            hit = contained[0]
            return {"folder_id": str(hit["id"]), "name": str(hit["name"])}
    mentions = [
        f
        for f in named
        if re.search(r"\b" + re.escape(str(f["name"])) + r"\b", text, re.I)
    ]
    if len(mentions) == 1:
        hit = mentions[0]
        return {"folder_id": str(hit["id"]), "name": str(hit["name"])}
    return None


def parse_note_suggestion(text: str) -> str:
    match = NOTE_LINE.search(text or "")
    return (match.group(1).strip() if match else "")


def build_filing_messages(
    *,
    title: str,
    when: str,
    hour: Any,
    mins: Any,
    notes: str | None,
    summary: str,
    transcript: str | None,
    folders: list[str],
    history: list[dict[str, str]],
    message: str,
) -> list[dict[str, str]]:
    context = (
        f"Title: {title}\n"
        f"When: {when} ({hour}:00), {mins} min\n"
        f"Notes: {notes or '(none)'}\n"
        f"Summary:\n{summary}\n"
    )
    if transcript:
        context += f"\nTranscript excerpt:\n{transcript}\n"
    turns: list[dict[str, str]] = []
    for row in history[-10:]:
        text = (row.get("text") or "").strip()
        if not text:
            continue
        role = "user" if row.get("role") == "user" else "assistant"
        turns.append({"role": role, "content": text})
    return [
        {"role": "system", "content": SYSTEM.format(folders=", ".join(folders))},
        {"role": "user", "content": context},
        *turns,
        {"role": "user", "content": message.strip()},
    ]


def _request_body(cfg: dict[str, str], messages: list[dict[str, str]], *, stream: bool) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": cfg["model"],
        "messages": messages,
        "max_tokens": 4096,
        "thinking": {"type": "enabled"},
        "reasoning_effort": "high",
        "stream": stream,
    }
    return body


def _post(cfg: dict[str, str], body: dict[str, Any], timeout: int) -> Any:
    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        cfg["url"],
        data=payload,
        headers={
            "Authorization": f"Bearer {cfg['key']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    return urllib.request.urlopen(req, timeout=timeout)


def complete_chat(messages: list[dict[str, str]]) -> tuple[str, str]:
    cfg = llm_config()
    if not cfg:
        return no_key_message(), ""
    body = _request_body(cfg, messages, stream=False)
    try:
        with _post(cfg, body, 120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        err = exc.read().decode("utf-8", errors="replace")[:300]
        return f"DeepSeek HTTP {exc.code}: {err}", ""
    except Exception as exc:
        return f"DeepSeek failed: {exc}", ""
    return parse_chat_message(data)


def iter_sse_data(lines: Iterator[bytes]) -> Iterator[dict[str, Any]]:
    for raw in lines:
        line = raw.strip()
        if not line.startswith(b"data:"):
            continue
        data = line[5:].strip()
        if data == b"[DONE]":
            return
        try:
            obj = json.loads(data.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if isinstance(obj, dict):
            yield obj


def delta_from_chunk(chunk: dict[str, Any]) -> tuple[str, str]:
    try:
        delta = chunk["choices"][0].get("delta") or {}
    except (KeyError, IndexError, TypeError, AttributeError):
        return "", ""
    thinking = str(delta.get("reasoning_content") or "")
    text = str(delta.get("content") or "")
    return thinking, text


def stream_chat(messages: list[dict[str, str]]) -> Iterator[dict[str, Any]]:
    cfg = llm_config()
    if not cfg:
        yield {"type": "error", "text": no_key_message()}
        return
    body = _request_body(cfg, messages, stream=True)
    thinking_parts: list[str] = []
    text_parts: list[str] = []
    try:
        with _post(cfg, body, 120) as resp:
            def _lines() -> Iterator[bytes]:
                while True:
                    line = resp.readline()
                    if not line:
                        return
                    yield line

            for chunk in iter_sse_data(_lines()):
                think, text = delta_from_chunk(chunk)
                if think:
                    thinking_parts.append(think)
                    yield {"type": "thinking", "delta": think}
                if text:
                    text_parts.append(text)
                    yield {"type": "text", "delta": text}
    except urllib.error.HTTPError as exc:
        err = exc.read().decode("utf-8", errors="replace")[:300]
        yield {"type": "error", "text": f"DeepSeek HTTP {exc.code}: {err}"}
        return
    except Exception as exc:
        yield {"type": "error", "text": f"DeepSeek failed: {exc}"}
        return
    text = "".join(text_parts).strip()
    thinking = "".join(thinking_parts).strip()
    if not text and thinking:
        text = thinking.split("\n\n")[-1].strip()
    yield {
        "type": "done",
        "text": text or "DeepSeek returned an empty reply.",
        "thinking": thinking,
    }
