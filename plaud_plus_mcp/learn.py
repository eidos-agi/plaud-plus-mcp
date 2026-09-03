"""Operational observations from Plaud Plus writes.

This is not lessons.md. Nothing here is CONFIRMED. Counts are guesses
to show an agent before it writes. Never auto-apply a suggestion.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

TOKEN = re.compile(r"[a-z0-9]{2,}")
CLOCK_TITLE = re.compile(r"^\d{4}-\d{2}-\d{2}(?:[ T_]\d{2}:\d{2}(?::\d{2})?)?$")
SKIP = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "this",
    "that",
    "plus",
    "mcp",
    "probe",
    "call",
    "meeting",
    "audio",
    "renamed",
    "an",
    "to",
    "of",
    "on",
    "in",
    "or",
    "vs",
    "is",
    "it",
    "ai",
    "new",
    "how",
    "use",
    "using",
    "due",
    "via",
    "note",
    "notes",
    "reminder",
    "idea",
    "demo",
    "briefing",
    "recording",
    "accidental",
    "reasoning",
    "session",
    "imported",
}


def ledger_path() -> Path:
    env = os.getenv("PLAUD_PLUS_LEARN")
    if env:
        return Path(env)
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/PlaudPlus/learn.jsonl"
    return Path.home() / ".local/share/plaud-plus/learn.jsonl"


def tokens(text: str | None) -> set[str]:
    if not text:
        return set()
    out: set[str] = set()
    for t in TOKEN.findall(text.lower()):
        if t in SKIP or t.isdigit() or re.fullmatch(r"20\d{2}", t):
            continue
        out.add(t)
    return out


def is_clock_title(title: str | None) -> bool:
    if not title:
        return False
    return bool(CLOCK_TITLE.match(title.strip()))


def _is_test_folder(name: str | None) -> bool:
    n = (name or "").lower()
    return "probe" in n or "test folder" in n


def append(event: dict[str, Any], path: Path | None = None) -> None:
    dest = path or ledger_path()
    dest.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": int(time.time()), **event}
    with dest.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, separators=(",", ":"), ensure_ascii=False) + "\n")


def read_events(path: Path | None = None, limit: int = 500) -> list[dict[str, Any]]:
    dest = path or ledger_path()
    if not dest.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in dest.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows[-limit:]


def record_tool(name: str, arguments: dict[str, Any], payload: dict[str, Any], path: Path | None = None) -> None:
    """Store a successful write. Skip reads and failed calls."""
    if not isinstance(payload, dict) or payload.get("ok") is False:
        return
    event: dict[str, Any] | None = None
    if name == "mutate_recording":
        action = arguments.get("action")
        event = {
            "kind": str(action or "mutate"),
            "recording_id": arguments.get("recording_id") or payload.get("recording_id"),
            "folder_id": arguments.get("folder_id") or payload.get("folder_id"),
            "title": arguments.get("new_name") or payload.get("new_name"),
        }
        if action == "move":
            event["kind"] = "move"
        elif action == "rename":
            event["kind"] = "rename"
    elif name == "mutate_folder":
        folder = payload.get("folder") if isinstance(payload.get("folder"), dict) else {}
        event = {
            "kind": "folder",
            "action": arguments.get("action") or payload.get("action"),
            "folder_id": arguments.get("folder_id") or folder.get("id") or payload.get("folder_id"),
            "name": arguments.get("name") or folder.get("name"),
            "color": arguments.get("color") or folder.get("color"),
        }
    elif name == "edit_transcript":
        action = arguments.get("action")
        if action == "rename_speaker":
            event = {
                "kind": "rename_speaker",
                "recording_id": arguments.get("recording_id"),
                "original_label": arguments.get("original_label"),
                "new_name": arguments.get("new_name"),
            }
        elif action == "correct" and not arguments.get("dry_run"):
            find, replace = arguments.get("find"), arguments.get("replace")
            if find and find != replace:
                event = {
                    "kind": "correct",
                    "target": "transcript",
                    "recording_id": arguments.get("recording_id"),
                    "find": find,
                    "replace": replace,
                }
    elif name == "edit_summary":
        if arguments.get("action") == "correct" and not arguments.get("dry_run"):
            find, replace = arguments.get("find"), arguments.get("replace")
            if find and find != replace:
                event = {
                    "kind": "correct",
                    "target": "summary",
                    "recording_id": arguments.get("recording_id"),
                    "find": find,
                    "replace": replace,
                }
    elif name == "upload_recording":
        event = {
            "kind": "upload",
            "recording_id": payload.get("recording_id"),
            "title": arguments.get("title"),
            "folder_id": arguments.get("folder_id"),
        }
    if event:
        event = {k: v for k, v in event.items() if v not in (None, "", [])}
        if event.get("kind"):
            append(event, path=path)


def remember(claim: str, *, extra: dict[str, Any] | None = None, path: Path | None = None) -> dict[str, Any]:
    claim = claim.strip()
    if not claim:
        raise ValueError("claim cannot be empty")
    event = {"kind": "note", "claim": claim, "confidence": "UNVERIFIED"}
    if extra:
        event.update(extra)
    append(event, path=path)
    return {"ok": True, "stored": event, "note": "UNVERIFIED observation, not a lessons.md CONFIRMED lesson"}


def snapshot_folders(folders: list[dict[str, Any]], path: Path | None = None) -> int:
    n = 0
    seen = {(e.get("folder_id"), e.get("name")) for e in read_events(path) if e.get("kind") == "folder"}
    for folder in folders:
        fid, name = folder.get("id") or folder.get("folder_id"), folder.get("name")
        if not fid or not name:
            continue
        key = (fid, name)
        if key in seen:
            continue
        append({"kind": "folder", "action": "seen", "folder_id": fid, "name": name, "color": folder.get("color")}, path=path)
        seen.add(key)
        n += 1
    return n


def snapshot_filings(recordings: list[dict[str, Any]], path: Path | None = None) -> int:
    """Ingest already-filed titles as UNVERIFIED move observations."""
    n = 0
    seen = {
        (e.get("recording_id"), e.get("folder_id"))
        for e in read_events(path)
        if e.get("kind") == "move" and e.get("recording_id") and e.get("folder_id")
    }
    for rec in recordings:
        fid = rec.get("folder_id")
        rid = rec.get("id") or rec.get("recording_id")
        title = rec.get("title") or rec.get("filename") or rec.get("new_name")
        if not fid or not rid:
            continue
        key = (rid, fid)
        if key in seen:
            continue
        append(
            {
                "kind": "move",
                "action": "seen",
                "recording_id": rid,
                "folder_id": fid,
                "title": title,
            },
            path=path,
        )
        seen.add(key)
        n += 1
    return n


def _folder_names(events: list[dict[str, Any]]) -> dict[str, str]:
    names: dict[str, str] = {}
    for e in events:
        fid, name = e.get("folder_id"), e.get("name")
        if isinstance(fid, str) and isinstance(name, str):
            names[fid] = name
    return names


def suggest(*, title: str | None = None, recording_id: str | None = None, path: Path | None = None) -> dict[str, Any]:
    events = read_events(path)
    names = _folder_names(events)
    clock = is_clock_title(title)
    hay = tokens(title)
    title_l = (title or "").lower()
    folder_scores: Counter[str] = Counter()
    if not clock:
        for e in events:
            if e.get("kind") == "move" and e.get("folder_id"):
                blob = tokens(str(e.get("title") or "")) | tokens(names.get(str(e["folder_id"]), ""))
                if hay and hay & blob:
                    folder_scores[str(e["folder_id"])] += 2
            if e.get("kind") == "folder" and e.get("folder_id") and e.get("name"):
                fname = str(e["name"])
                if _is_test_folder(fname) and "probe" not in title_l:
                    continue
                if hay and hay & tokens(fname):
                    folder_scores[str(e["folder_id"])] += 3
            if e.get("kind") == "note":
                fid = e.get("folder_id")
                terms = e.get("terms") if isinstance(e.get("terms"), list) else []
                term_hit = any(
                    isinstance(term, str) and len(term) >= 3 and term.lower() in title_l for term in terms
                )
                if term_hit and isinstance(fid, str):
                    folder_scores[fid] += 4
                elif isinstance(fid, str) and hay and hay & tokens(str(e.get("claim") or "")):
                    folder_scores[fid] += 2
    speakers: Counter[tuple[str, str]] = Counter()
    for e in events:
        if e.get("kind") == "rename_speaker" and e.get("original_label") and e.get("new_name"):
            speakers[(str(e["original_label"]), str(e["new_name"]))] += 1
    corrections: Counter[tuple[str, str, str]] = Counter()
    for e in events:
        if e.get("kind") == "correct" and e.get("find") and e.get("replace"):
            corrections[(str(e.get("target") or "transcript"), str(e["find"]), str(e["replace"]))] += 1

    folder_guess = []
    for fid, score in folder_scores.most_common(5):
        if _is_test_folder(names.get(fid)) and "probe" not in title_l:
            continue
        folder_guess.append({"folder_id": fid, "name": names.get(fid), "score": score})
    speaker_guess = [
        {"original_label": a, "new_name": b, "count": n} for (a, b), n in speakers.most_common(8)
    ]
    correct_guess = [
        {"target": t, "find": f, "replace": r, "count": n} for (t, f, r), n in corrections.most_common(8)
    ]
    return {
        "ok": True,
        "recording_id": recording_id,
        "title": title,
        "confidence": "UNVERIFIED",
        "do_not_apply": True,
        "folders": folder_guess,
        "speakers": speaker_guess,
        "corrections": correct_guess,
        "events": len(events),
        "clock_title": clock,
        "note": (
            "Clock title — do not guess a tenant from the timestamp."
            if clock
            else "Guesses from local write history. Ask the human before mutate_recording / edit_transcript."
        ),
    }


def status(path: Path | None = None) -> dict[str, Any]:
    events = read_events(path)
    kinds = Counter(str(e.get("kind") or "unknown") for e in events)
    return {
        "ok": True,
        "path": str(path or ledger_path()),
        "events": len(events),
        "kinds": dict(kinds),
        "confidence": "UNVERIFIED",
        "note": "Operational ledger, not lessons.md. CONFIRMED is illegal here.",
    }


def recall(*, kind: str | None = None, limit: int = 20, path: Path | None = None) -> dict[str, Any]:
    events = read_events(path)
    if kind:
        events = [e for e in events if e.get("kind") == kind]
    return {"ok": True, "events": events[-limit:], "count": len(events)}
