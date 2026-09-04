"""Mini HITL trainer: one unfiled recording, human picks a folder, model refits.

Local only. Never files without a click. Not lessons.md CONFIRMED.
Filing chat is our own DeepSeek harness — not DSH, not a coding agent.
"""

from __future__ import annotations

import json
import sys
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import parse_qs, urlparse

from .auth import AuthError, ensure_session
from .harness import (
    build_filing_messages,
    llm_config,
    parse_folder_suggestion,
    stream_chat,
)
from .learn import (
    _is_test_folder,
    extract_people,
    extract_places,
    fit,
    ledger_path,
    remember,
    snapshot_filings,
    snapshot_folders,
    suggest,
)

STATIC = Path(__file__).parent / "static"
MIME = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
}


def static_bytes(name: str) -> bytes:
    path = (STATIC / name).resolve()
    if path.parent != STATIC.resolve() or not path.is_file():
        raise FileNotFoundError(name)
    return path.read_bytes()


def page_bundle() -> str:
    return "".join(
        (STATIC / name).read_text(encoding="utf-8")
        for name in ("train.html", "train.css", "train.js")
    )


def chats_dir() -> Path:
    return ledger_path().parent / "chats"


def chat_path(recording_id: str) -> Path:
    return chats_dir() / f"{recording_id}.jsonl"


def load_chat(recording_id: str) -> list[dict[str, str]]:
    dest = chat_path(recording_id)
    if not dest.is_file():
        return []
    rows: list[dict[str, str]] = []
    for line in dest.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and obj.get("role"):
            rows.append(obj)
    return rows


def append_chat(recording_id: str, message: dict[str, Any]) -> None:
    dest = chat_path(recording_id)
    dest.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": int(datetime.now().timestamp()), **message}
    with dest.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def tape_fields(body: str | None, trans: str | None, utterances: Any = None) -> dict[str, Any]:
    """Summary stays short. Transcript is the full string — never sliced."""
    out: dict[str, Any] = {"body_preview": (body or "")[:400]}
    if trans:
        out["transcript"] = trans
        out["deep"] = True
        out["transcript_chars"] = len(trans)
        if isinstance(utterances, int):
            out["utterances"] = utterances
    return out


def folder_buttons(folders: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for folder in folders:
        name = folder.get("name")
        if _is_test_folder(name):
            continue
        fid = folder.get("id") or folder.get("folder_id")
        if not fid:
            continue
        out.append({"id": fid, "name": name, "color": folder.get("color") or "#888"})
    return out


def recording_view(rec: dict[str, Any], body: str | None, hour: int | None) -> dict[str, Any]:
    title = rec.get("title") or rec.get("filename") or "(untitled)"
    blob = f"{title}\n{body or ''}"
    when = rec.get("when")
    if not when and rec.get("date"):
        when = str(rec["date"]).replace("T", " ")
    if hour is not None and not when:
        when = f"{hour:02d}:00"
    return {
        "id": rec.get("id") or rec.get("recording_id"),
        "title": title,
        "when": when or "",
        "mins": rec.get("mins") or rec.get("duration_minutes") or 0,
        "people": sorted(extract_people(blob)),
        "places": sorted(extract_places(blob)),
        "clock": bool(rec.get("clock")),
    }


class TrainSession:
    def __init__(self) -> None:
        from plaud_tools.core.client import PlaudClient
        from plaud_tools.core.session import SessionManager, SessionStore

        ensure_session()
        self.client = PlaudClient(SessionManager(SessionStore()))
        self.queue: list[dict[str, Any]] = []
        self.labeled = 0
        self.trashed = 0
        self._cache: dict[str, Any] = {}
        self._folders: list[dict[str, Any]] = []
        self._refresh_meta()
        self._refresh_queue()

    def _refresh_meta(self) -> None:
        tags = self.client.list_file_tags()
        self._folders = [{"id": t.id, "name": t.name, "color": t.color} for t in tags]
        snapshot_folders(self._folders)

    def _refresh_queue(self) -> None:
        from plaud_tools.core.client import PlaudRecordingQuery
        from plaud_tools.core.query import summarize_recording

        recs = []
        skip = 0
        while True:
            batch = self.client.list_recordings(
                PlaudRecordingQuery(skip=skip, limit=200, is_trash=0, sort_by="start_time", is_desc=True)
            )
            if not batch:
                break
            recs.extend(batch)
            if len(batch) < 200:
                break
            skip += 200
        self.queue = []
        for item in recs:
            if item.filetag_id_list:
                continue
            summary = summarize_recording(item)
            dt = datetime.fromtimestamp(item.start_time / 1000)
            hour12 = dt.hour % 12 or 12
            ampm = "AM" if dt.hour < 12 else "PM"
            summary["when"] = f"{dt.strftime('%a')} {hour12}:{dt.minute:02d} {ampm}"
            summary["hour"] = dt.hour
            summary["mins"] = summary.get("duration_minutes") or 0
            self.queue.append(summary)

    def _enrich(self, rec: dict[str, Any], *, transcript: bool = False) -> dict[str, Any]:
        rid = rec["id"]
        cached = self._cache if self._cache.get("id") == rid else {}
        if cached.get("ready") and (not transcript or cached.get("deep")):
            return cached
        detail = self.client.get_recording(
            rid,
            include_summary=True,
            include_transcript=transcript,
        )
        extra = detail.extra_data or {}
        headline = (extra.get("aiContentHeader") or {}).get("headline")
        body = detail.ai_content if isinstance(detail.ai_content, str) else None
        if headline and (not body or headline not in body):
            body = f"{headline}\n{body or ''}"
        hour = rec.get("hour")
        start = getattr(detail, "start_time", None)
        if isinstance(start, (int, float)) and start > 0:
            ts = start / 1000 if start > 10_000_000_000 else start
            hour = datetime.fromtimestamp(ts).hour
        speakers = list(getattr(detail, "speakers", None) or [])
        trans = getattr(detail, "transcript", None) if transcript else cached.get("transcript")
        segs = getattr(detail, "transcript_segments", None) if transcript else None
        out = {
            "id": rid,
            "ready": True,
            "deep": bool(transcript) or bool(cached.get("deep")),
            "body": body,
            "headline": headline,
            "hour": hour,
            "speakers": speakers,
            "transcript": trans if isinstance(trans, str) else cached.get("transcript"),
            "utterances": len(segs) if isinstance(segs, list) else cached.get("utterances"),
        }
        self._cache = out
        return out

    def _filing_messages(self, rec: dict[str, Any], message: str, notes: str | None) -> list[dict[str, str]]:
        info = self._enrich(rec)
        buttons = folder_buttons(self._folders)
        return build_filing_messages(
            title=str(rec.get("title") or ""),
            when=str(rec.get("when") or ""),
            hour=info.get("hour"),
            mins=rec.get("mins"),
            notes=notes,
            summary=(info.get("body") or "")[:2500],
            transcript=((info.get("transcript") or "")[:2500] or None),
            folders=[f["name"] for f in buttons],
            history=load_chat(str(rec.get("id"))),
            message=message,
        )

    def card(self) -> dict[str, Any]:
        buttons = folder_buttons(self._folders)
        base = {
            "folders": buttons,
            "labeled": self.labeled,
            "trashed": self.trashed,
            "left": len(self.queue),
        }
        if not self.queue:
            return {**base, "done": True}
        rec = self.queue[0]
        try:
            info = self._enrich(rec)
        except Exception as exc:
            return {**base, "error": str(exc), "recording": recording_view(rec, None, rec.get("hour"))}
        body = info.get("body")
        trans = info.get("transcript")
        combined = "\n\n".join(p for p in (body, trans) if p)
        hour = info.get("hour")
        guess = suggest(title=rec.get("title"), body=combined or body, recording_id=rec.get("id"), hour=hour)
        view = recording_view(rec, combined or body, hour)
        view["headline"] = info.get("headline")
        view["speakers"] = info.get("speakers") or []
        chat = load_chat(str(rec.get("id")))
        harness_guess = None
        for row in reversed(chat):
            if row.get("role") == "assistant" and row.get("text"):
                harness_guess = parse_folder_suggestion(str(row["text"]), buttons)
                break
        payload = {
            **base,
            "done": False,
            "recording": view,
            "guess": guess,
            "harness_guess": harness_guess,
            "body_preview": (body or "")[:400],
            "chat": chat,
        }
        payload.update(tape_fields(body, trans if isinstance(trans, str) else None, info.get("utterances")))
        cfg = llm_config()
        if cfg:
            payload["chat_model"] = f"DeepSeek {cfg['model']}"
        else:
            payload["chat_model"] = "DeepSeek (no key)"
        return payload

    def _keep_note(
        self,
        rec: dict[str, Any],
        notes: str | None,
        *,
        folder_id: str | None = None,
        action: str | None = None,
    ) -> str:
        text = (notes or "").strip()
        if not text:
            return ""
        extra: dict[str, Any] = {
            "recording_id": rec.get("id"),
            "title": rec.get("title"),
        }
        if folder_id:
            extra["folder_id"] = folder_id
        if action:
            extra["action"] = action
        remember(text, extra=extra)
        return text

    def skip(self, notes: str | None = None) -> dict[str, Any]:
        if self.queue:
            rec = self.queue[0]
            self._keep_note(rec, notes, action="skip")
            self.queue.pop(0)
        self._cache = {}
        return self.card()

    def chat(self, recording_id: str, message: str, notes: str | None = None) -> dict[str, Any]:
        for _ in self.chat_events(recording_id, message, notes):
            pass
        if not self.queue or self.queue[0].get("id") != recording_id:
            return {"error": "stale card; reload", "labeled": self.labeled, "left": len(self.queue)}
        return self.card()

    def chat_events(
        self, recording_id: str, message: str, notes: str | None = None
    ) -> Iterator[dict[str, Any]]:
        if not self.queue or self.queue[0].get("id") != recording_id:
            yield {"type": "error", "text": "stale card; reload"}
            return
        rec = self.queue[0]
        packed = self._filing_messages(rec, message, notes)
        append_chat(recording_id, {"role": "user", "text": message.strip()})
        thinking = ""
        reply = ""
        failed = False
        for ev in stream_chat(packed):
            kind = ev.get("type")
            if kind == "thinking":
                thinking += str(ev.get("delta") or "")
                yield ev
            elif kind == "text":
                reply += str(ev.get("delta") or "")
                yield ev
            elif kind == "error":
                reply = str(ev.get("text") or "Harness failed.")
                failed = True
                yield ev
            elif kind == "done":
                reply = str(ev.get("text") or reply)
                thinking = str(ev.get("thinking") or thinking)
        append_chat(
            recording_id,
            {"role": "assistant", "text": reply, "thinking": thinking},
        )
        if failed:
            return
        buttons = folder_buttons(self._folders)
        yield {
            "type": "done",
            "text": reply,
            "thinking": thinking,
            "suggestion": parse_folder_suggestion(reply, buttons),
        }

    def deepen(self, recording_id: str) -> dict[str, Any]:
        if not self.queue or self.queue[0].get("id") != recording_id:
            return {"error": "stale card; reload", "labeled": self.labeled, "left": len(self.queue)}
        self._enrich(self.queue[0], transcript=True)
        return self.card()

    def trash(self, recording_id: str, notes: str | None = None) -> dict[str, Any]:
        if not self.queue or self.queue[0].get("id") != recording_id:
            return {"error": "stale card; reload", "labeled": self.labeled, "left": len(self.queue)}
        rec = self.queue[0]
        self._keep_note(rec, notes, action="trash")
        self.client.move_to_trash(recording_id)
        self.queue.pop(0)
        self.trashed += 1
        self._cache = {}
        return self.card()

    def label(self, recording_id: str, folder_id: str, notes: str | None = None) -> dict[str, Any]:
        allowed = {f["id"] for f in folder_buttons(self._folders)}
        if folder_id not in allowed:
            return {"error": "unknown folder", "labeled": self.labeled, "left": len(self.queue)}
        if not self.queue or self.queue[0].get("id") != recording_id:
            return {"error": "stale card; reload", "labeled": self.labeled, "left": len(self.queue)}
        rec = self.queue[0]
        info = self._enrich(rec)
        note = self._keep_note(rec, notes, folder_id=folder_id, action="label")
        self.client.set_recording_folder(recording_id, folder_id)
        body_parts = [p for p in (info.get("body"), info.get("transcript")) if p]
        if note:
            body_parts.append(f"Trainer note: {note}")
        chat_lines = [
            f"{m.get('role')}: {m.get('text')}"
            for m in load_chat(recording_id)
            if m.get("text")
        ]
        if chat_lines:
            body_parts.append("Trainer chat:\n" + "\n".join(chat_lines[-12:]))
        snapshot_filings(
            [
                {
                    "id": recording_id,
                    "folder_id": folder_id,
                    "title": rec.get("title"),
                    "headline": info.get("headline"),
                    "body": "\n\n".join(body_parts),
                    "hour": info.get("hour"),
                }
            ]
        )
        fit()
        self.queue.pop(0)
        self.labeled += 1
        self._cache = {}
        return self.card()


_SESSION: TrainSession | None = None
_LOCK = threading.Lock()


def _session() -> TrainSession:
    global _SESSION
    with _LOCK:
        if _SESSION is None:
            _SESSION = TrainSession()
        return _SESSION


class TrainHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("plus-train: " + (fmt % args) + "\n")

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, payload: dict[str, Any]) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send(code, raw, "application/json; charset=utf-8")

    def _sse(self, events: Iterator[dict[str, Any]]) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            for ev in events:
                line = "data: " + json.dumps(ev, ensure_ascii=False) + "\n\n"
                self.wfile.write(line.encode("utf-8"))
                self.wfile.flush()
        except BrokenPipeError:
            return

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            self._send(200, static_bytes("train.html"), MIME[".html"])
            return
        if path in ("/train.css", "/train.js"):
            name = path.lstrip("/")
            ext = Path(name).suffix
            try:
                self._send(200, static_bytes(name), MIME[ext])
            except FileNotFoundError:
                self._send(404, b"not found", "text/plain")
            return
        if path == "/api/card":
            try:
                self._json(200, _session().card())
            except AuthError as exc:
                self._json(401, {"error": str(exc)})
            except Exception as exc:
                self._json(500, {"error": str(exc)})
            return
        if path == "/api/chat":
            qs = parse_qs(urlparse(self.path).query)
            rid = (qs.get("recording_id") or [None])[0]
            hist = load_chat(str(rid)) if rid else []
            self._json(200, {"chat": hist})
            return
        self._send(404, b"not found", "text/plain")

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._json(400, {"error": "invalid json"})
            return
        try:
            sess = _session()
            if path == "/api/skip":
                self._json(200, sess.skip(notes=payload.get("notes")))
                return
            if path == "/api/chat/stream":
                rid = payload.get("recording_id")
                msg = payload.get("message")
                if not rid or not msg:
                    self._json(400, {"error": "recording_id and message required"})
                    return
                self._sse(sess.chat_events(str(rid), str(msg), notes=payload.get("notes")))
                return
            if path == "/api/chat":
                rid = payload.get("recording_id")
                msg = payload.get("message")
                if not rid or not msg:
                    self._json(400, {"error": "recording_id and message required"})
                    return
                self._json(200, sess.chat(str(rid), str(msg), notes=payload.get("notes")))
                return
            if path == "/api/deepen":
                rid = payload.get("recording_id")
                if not rid:
                    self._json(400, {"error": "recording_id required"})
                    return
                self._json(200, sess.deepen(str(rid)))
                return
            if path == "/api/trash":
                rid = payload.get("recording_id")
                if not rid:
                    self._json(400, {"error": "recording_id required"})
                    return
                self._json(200, sess.trash(str(rid), notes=payload.get("notes")))
                return
            if path == "/api/label":
                rid = payload.get("recording_id")
                fid = payload.get("folder_id")
                if not rid or not fid:
                    self._json(400, {"error": "recording_id and folder_id required"})
                    return
                self._json(200, sess.label(str(rid), str(fid), notes=payload.get("notes")))
                return
        except AuthError as exc:
            self._json(401, {"error": str(exc)})
            return
        except Exception as exc:
            self._json(500, {"error": str(exc)})
            return
        self._send(404, b"not found", "text/plain")


def serve(host: str = "127.0.0.1", port: int = 7843, *, open_browser: bool = True) -> int:
    import webbrowser

    try:
        ensure_session()
    except AuthError as exc:
        print(f"plaud-plus: {exc}", file=sys.stderr)
        return 2
    httpd = ThreadingHTTPServer((host, port), TrainHandler)
    url = f"http://{host}:{port}/"
    print(f"plus train: {url}", file=sys.stderr)
    print("Filing harness · Y agree · S skip · D deeper · T trash (twice).", file=sys.stderr)
    if open_browser:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nplus train: stopped", file=sys.stderr)
    finally:
        httpd.server_close()
    return 0
