"""Mini HITL trainer: one unfiled recording, human picks a folder, model refits.

Local only. Never files without a click. Not lessons.md CONFIRMED.
"""

from __future__ import annotations

import json
import sys
import threading
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from .auth import AuthError, ensure_session
from .learn import (
    _is_test_folder,
    extract_people,
    extract_places,
    fit,
    remember,
    snapshot_filings,
    snapshot_folders,
    suggest,
)

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Plus train</title>
<style>
  :root {
    --ink: #1c140c;
    --paper: #f3ead8;
    --rule: #cbb892;
    --mute: #6e5c3e;
    --yes: #1c140c;
  }
  * { box-sizing: border-box; }
  html, body { height: 100%; margin: 0; }
  body {
    font-family: Palatino, "Palatino Linotype", "Iowan Old Style", "Times New Roman", serif;
    background: var(--ink);
    color: var(--ink);
    min-height: 100%;
  }
  .stage {
    min-height: 100%;
    display: flex;
    flex-direction: column;
    padding: 28px 22px 40px;
    max-width: 720px;
    margin: 0 auto;
  }
  header {
    color: #e8d7b0;
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    font-size: 13px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin-bottom: 18px;
  }
  header strong { letter-spacing: 0.16em; }
  .card {
    background: var(--paper);
    border-radius: 2px;
    padding: 28px 28px 24px;
    box-shadow: 8px 10px 0 #000;
    flex: 1;
  }
  .meta {
    color: var(--mute);
    font-size: 14px;
    margin: 0 0 10px;
  }
  h1 {
    font-size: clamp(1.4rem, 3vw, 2rem);
    line-height: 1.2;
    margin: 0 0 16px;
    font-weight: 600;
  }
  .chips { display: flex; flex-wrap: wrap; gap: 6px; margin: 0 0 18px; }
  .chip {
    border: 1px solid var(--rule);
    padding: 3px 9px;
    font-size: 13px;
    color: var(--mute);
  }
  .blurb {
    font-size: 15px;
    line-height: 1.45;
    color: #3d2f18;
    margin: 0 0 16px;
    max-height: 7.5em;
    overflow: hidden;
  }
  .guess {
    font-style: italic;
    color: var(--mute);
    margin: 0 0 22px;
    font-size: 15px;
  }
  .guess b { font-style: normal; color: var(--ink); }
  .note {
    display: block;
    width: 100%;
    min-height: 5.5em;
    margin: 0 0 18px;
    padding: 10px 12px;
    border: 0;
    border-top: 1px solid var(--rule);
    border-bottom: 1px solid var(--rule);
    background: #efe6d0;
    color: var(--ink);
    font-family: inherit;
    font-size: 16px;
    line-height: 1.4;
    resize: vertical;
  }
  .note:focus { outline: 2px solid var(--ink); outline-offset: -2px; }
  .note::placeholder { color: #9a855c; }
  .folders { display: flex; flex-direction: column; gap: 8px; }
  button {
    font-family: inherit;
    font-size: 17px;
    text-align: left;
    padding: 12px 14px;
    border: 0;
    cursor: pointer;
    background: #fff8ea;
    color: var(--ink);
    border-left: 8px solid #888;
  }
  button.yes {
    background: var(--yes);
    color: var(--paper);
    font-size: 19px;
    padding: 16px 16px;
  }
  button:disabled { opacity: 0.4; cursor: wait; }
  .more {
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
    margin-top: 16px;
    align-items: center;
  }
  .skip, .deep, .trash {
    background: none;
    border: 0;
    color: var(--mute);
    padding: 0;
    font-size: 15px;
    text-decoration: underline;
    cursor: pointer;
    font-family: inherit;
  }
  .trash { color: #8a2f1f; }
  .trash.armed { color: #c0392b; font-weight: 600; text-decoration: none; }
  .blurb.deep {
    max-height: 22em;
    overflow: auto;
    white-space: pre-wrap;
    font-size: 14px;
    border-top: 1px solid var(--rule);
    padding-top: 12px;
  }
  .empty { color: var(--paper); padding: 40px 8px; }
  .err { color: #ffb4a2; margin: 12px 0; }
  kbd {
    font-family: ui-monospace, Menlo, monospace;
    font-size: 11px;
    border: 1px solid var(--rule);
    padding: 0 5px;
    margin-left: 8px;
    color: var(--mute);
  }
  button.yes kbd { color: #cbb892; border-color: #6e5c3e; }
</style>
</head>
<body>
  <div class="stage">
    <header>
      <strong>Plus train</strong>
      <span id="stats">…</span>
    </header>
    <div id="root">loading</div>
  </div>
<script>
let card = null;
const notesById = {};
async function load() {
  const r = await fetch("/api/card");
  card = await r.json();
  draw();
}
function draw() {
  trashArmed = false;
  const el = document.getElementById("root");
  const st = document.getElementById("stats");
  st.textContent = (card.labeled ?? 0) + " labeled · " + (card.trashed ?? 0) + " trash · " + (card.left ?? 0) + " left";
  if (card.error) {
    el.innerHTML = '<p class="err"></p>';
    el.querySelector(".err").textContent = card.error;
    return;
  }
  if (card.done) {
    el.innerHTML = '<div class="empty"><h1>Queue is empty.</h1><p>Labeled this session: '
      + (card.labeled ?? 0) + "</p></div>";
    return;
  }
  const rec = card.recording;
  const guess = (card.guess && card.guess.folders && card.guess.folders[0]) || null;
  const people = (rec.people || []).map(p => '<span class="chip"></span>');
  const folders = card.folders || [];
  let html = '<div class="card">';
  html += '<p class="meta"></p>';
  html += "<h1></h1>";
  html += '<div class="chips" id="chips"></div>';
  html += '<p class="blurb" id="blurb"></p>';
  html += '<p class="guess"></p>';
  html += '<textarea class="note" id="note" placeholder="Who was there, where, what this actually is…"></textarea>';
  html += '<div class="folders" id="folders"></div>';
  html += '<div class="more">';
  html += '<button class="skip" id="skip">Skip <kbd>S</kbd></button>';
  html += '<button class="deep" id="deep">Dive deeper <kbd>D</kbd></button>';
  html += '<button class="trash" id="trash">Trash <kbd>T</kbd></button>';
  html += "</div></div>";
  el.innerHTML = html;
  el.querySelector(".meta").textContent = rec.when + " · " + rec.mins + " min";
  el.querySelector("h1").textContent = rec.title;
  const chips = el.querySelector("#chips");
  (rec.people || []).forEach(p => {
    const s = document.createElement("span");
    s.className = "chip";
    s.textContent = p;
    chips.appendChild(s);
  });
  (rec.places || []).forEach(p => {
    const s = document.createElement("span");
    s.className = "chip";
    s.textContent = p;
    chips.appendChild(s);
  });
  const blurb = el.querySelector("#blurb");
  const preview = card.deep_text || card.body_preview;
  if (preview) {
    blurb.textContent = preview;
    if (card.deep_text) blurb.classList.add("deep");
  } else blurb.remove();
  const g = el.querySelector(".guess");
  if (guess) {
    const why = (guess.why || []).slice(0, 4).map(w => w.term).join(", ");
    g.innerHTML = "model leans <b></b>" + (why ? " — " + why : "");
    g.querySelector("b").textContent = guess.name || "?";
  } else {
    g.textContent = "no guess — you pick";
  }
  const box = el.querySelector("#folders");
  folders.forEach((f, i) => {
    const b = document.createElement("button");
    const isYes = guess && f.id === guess.folder_id;
    b.className = isYes ? "yes" : "";
    b.style.borderLeftColor = f.color || "#888";
    b.textContent = (isYes ? "Yes — " : "") + f.name;
    const k = document.createElement("kbd");
    k.textContent = isYes ? "Y" : String(i + 1);
    b.appendChild(k);
    b.onclick = () => label(f.id, b);
    box.appendChild(b);
  });
  const note = el.querySelector("#note");
  note.value = notesById[rec.id] || "";
  note.addEventListener("input", () => { notesById[rec.id] = note.value; });
  el.querySelector("#skip").onclick = () => skip();
  el.querySelector("#deep").onclick = () => deepen();
  const trashBtn = el.querySelector("#trash");
  trashBtn.onclick = () => trashClick(trashBtn);
}
function noteText() {
  const t = document.getElementById("note");
  const v = t ? t.value : (card && card.recording ? notesById[card.recording.id] : "") || "";
  if (card && card.recording) notesById[card.recording.id] = v;
  return v.trim();
}
let trashArmed = false;
function trashClick(btn) {
  if (!trashArmed) {
    trashArmed = true;
    btn.classList.add("armed");
    btn.textContent = "Trash for real?";
    const k = document.createElement("kbd");
    k.textContent = "T";
    btn.appendChild(k);
    return;
  }
  trashArmed = false;
  trash();
}
async function label(folderId, btn) {
  document.querySelectorAll("button").forEach(b => b.disabled = true);
  const r = await fetch("/api/label", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({ recording_id: card.recording.id, folder_id: folderId, notes: noteText() }),
  });
  card = await r.json();
  draw();
}
async function skip() {
  trashArmed = false;
  const r = await fetch("/api/skip", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({ recording_id: card.recording && card.recording.id, notes: noteText() }),
  });
  card = await r.json();
  draw();
}
async function deepen() {
  const r = await fetch("/api/deepen", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({ recording_id: card.recording.id, notes: noteText() }),
  });
  card = await r.json();
  draw();
}
async function trash() {
  document.querySelectorAll("button").forEach(b => b.disabled = true);
  const r = await fetch("/api/trash", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({ recording_id: card.recording.id, notes: noteText() }),
  });
  card = await r.json();
  draw();
}
document.addEventListener("keydown", (e) => {
  if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA" || !card || !card.recording) return;
  if (e.key === "s" || e.key === "S") { skip(); return; }
  if (e.key === "d" || e.key === "D") { deepen(); return; }
  if (e.key === "t" || e.key === "T") {
    const btn = document.getElementById("trash");
    if (btn) trashClick(btn);
    return;
  }
  if ((e.key === "y" || e.key === "Y") && card.guess && card.guess.folders && card.guess.folders[0]) {
    label(card.guess.folders[0].folder_id);
    return;
  }
  const n = parseInt(e.key, 10);
  if (n >= 1 && card.folders && card.folders[n - 1]) label(card.folders[n - 1].id);
});
load();
</script>
</body>
</html>
"""


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
        if isinstance(trans, str) and len(trans) > 12000:
            trans = trans[:12000] + "\n…"
        out = {
            "id": rid,
            "ready": True,
            "deep": bool(transcript) or bool(cached.get("deep")),
            "body": body,
            "headline": headline,
            "hour": hour,
            "speakers": speakers,
            "transcript": trans if isinstance(trans, str) else cached.get("transcript"),
        }
        self._cache = out
        return out

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
        payload = {
            **base,
            "done": False,
            "recording": view,
            "guess": guess,
            "body_preview": (body or "")[:400],
        }
        if trans:
            payload["deep_text"] = combined[:8000]
            payload["deep"] = True
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

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
            return
        if path == "/api/card":
            try:
                self._json(200, _session().card())
            except AuthError as exc:
                self._json(401, {"error": str(exc)})
            except Exception as exc:
                self._json(500, {"error": str(exc)})
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
    try:
        ensure_session()
    except AuthError as exc:
        print(f"plaud-plus: {exc}", file=sys.stderr)
        return 2
    httpd = ThreadingHTTPServer((host, port), TrainHandler)
    url = f"http://{host}:{port}/"
    print(f"plus train: {url}", file=sys.stderr)
    print("Y agree · S skip · D deeper · T trash (twice). Folder keys 1–5.", file=sys.stderr)
    if open_browser:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nplus train: stopped", file=sys.stderr)
    finally:
        httpd.server_close()
    return 0
