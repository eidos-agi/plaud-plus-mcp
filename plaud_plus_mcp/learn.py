"""Operational observations from Plaud Plus writes.

This is not lessons.md. Nothing here is CONFIRMED. Counts are guesses
to show an agent before it writes. Never auto-apply a suggestion.
"""

from __future__ import annotations

import json
import math
import os
import re
import sys
import tempfile
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

TOKEN = re.compile(r"[a-z0-9]{2,}")
CLOCK_TITLE = re.compile(r"^\d{4}-\d{2}-\d{2}(?:[ T_]\d{2}:\d{2}(?::\d{2})?)?$")
PROPER = re.compile(r"\b[A-Z][a-zA-Z]{2,}(?:[ -][A-Z][a-zA-Z0-9]{2,}){0,3}\b")
HOST = re.compile(r"\b[a-z0-9][a-z0-9.-]+\.[a-z]{2,}\b")
ENTITY_SKIP = {
    "meeting",
    "action",
    "items",
    "speaker",
    "core",
    "synopsis",
    "location",
    "insert",
    "names",
    "topic",
    "conclusion",
    "description",
    "overview",
    "background",
    "participants",
    "title",
    "date",
    "time",
    "next",
    "arrangements",
    "suggestions",
    "issues",
    "section",
    "speaker",
    "insert name",
    "action items",
    "core synopsis",
    "ai suggestions",
    "meeting notes",
    "meeting information",
}
GENERIC_UNIGRAMS = {
    "workflow",
    "application",
    "management",
    "process",
    "system",
    "budget",
    "planning",
    "monitoring",
    "workers",
    "office",
    "selection",
    "requirements",
    "optimizing",
    "construction",
    "plugin",
    "replacement",
    "portfolio",
    "pay",
    "real",
    "data",
    "tool",
    "board",
    "engine",
    "availability",
    "failover",
    "cards",
    "automated",
    "casual",
    "conversation",
    "workaround",
    "neighborhood",
    "team",
    "file",
    "index",
    "search",
    "tags",
    "apple",
    "excel",
    "files",
    "reporting",
    "development",
}
GENERIC_PHRASES = {
    "customer consultation",
    "weekly meeting",
    "reasoning note",
}
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
    "customer",
    "consultation",
    "dashboard",
    "participants",
    "speaker",
    "summary",
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


def _term_in(term: str, text: str) -> bool:
    """Phrase match. Short tokens need a word boundary so 'sid' ≠ 'sidebar'."""
    needle = term.lower().strip()
    if len(needle) < 3:
        return False
    if " " in needle or "." in needle or len(needle) >= 6:
        return needle in text
    return re.search(rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])", text) is not None


PERSON_STOP = {
    "the",
    "this",
    "that",
    "your",
    "core",
    "action",
    "meeting",
    "insert",
    "speaker",
    "next",
    "key",
    "new",
    "general",
    "initial",
    "problem",
    "date",
    "location",
    "participants",
    "overview",
    "background",
    "reminder",
    "idea",
    "demo",
    "briefing",
    "note",
    "weekly",
    "casual",
    "customer",
    "pilot",
    "using",
    "index",
    "draft",
    "showing",
    "microsoft",
    "apple",
    "claude",
    "anthracite",
    "universal",
    "atlas",
    "central",
    "reporting",
    "automated",
    "daniel",
    "shanklin",
    "plaud",
    "excel",
    "sidebar",
    "setup",
    "tactical",
    "accelerated",
    "holdings",
    "integration",
    "whatever",
    "remind",
    "research",
    "things",
    "remember",
    "their",
    "they",
    "hours",
    "title",
    "coordinating",
    "synopsis",
    "august",
    "outlook",
    "double",
    "prepare",
    "unassigned",
    "plans",
    "branch",
    "algorithm",
    "stocks",
    "imported",
    "recording",
    "single",
    "primary",
    "current",
    "data",
    "topic",
    "description",
    "each",
    "cards",
    "reliability",
    "define",
    "proposed",
    "ensure",
    "communicate",
    "identify",
    "approval",
    "suggestions",
    "planning",
    "presentation",
    "another",
    "send",
    "add",
    "set",
    "bird",
    "notes",
    "device",
    "workaround",
    "capturing",
    "audio",
    "plot",
    "system",
    "ingestion",
    "core",
}
ORG_TAIL = {
    "partners",
    "holdings",
    "realty",
    "system",
    "dashboard",
    "meeting",
    "notes",
    "plugin",
    "workflow",
    "process",
    "allocation",
    "integration",
    "development",
    "engine",
    "city",
    "street",
    "park",
    "national",
}
NAME2 = re.compile(r"\b([A-Z][a-z]+)\s+([A-Z][a-z]+)\b")
POSSESSIVE = re.compile(r"\b([A-Z][A-Za-z\-]+)'s\b")
FOR_TO_WITH = re.compile(r"\b(?:to|for|with)\s+([A-Z][a-z]{2,})\b")
PLACE_RE = re.compile(
    r"\b(home|neighborhood|zion(?:\s+national\s+park)?|vegas|"
    r"st\.?\s*george|texas|crested butte|fort worth|denton|host stand)\b",
    re.I,
)


def extract_people(text: str | None) -> set[str]:
    """People names from title/summary. Not folder IDs — context comes later."""
    if not text:
        return set()
    found: set[str] = set()
    for first, last in NAME2.findall(text):
        if first.lower() in PERSON_STOP or last.lower() in PERSON_STOP or last.lower() in ORG_TAIL:
            continue
        found.add(f"{first.lower()} {last.lower()}")
        found.add(first.lower())
    for match in POSSESSIVE.finditer(text):
        token = match.group(1).lower()
        if token not in PERSON_STOP and len(token) >= 3:
            found.add(token)
    for match in FOR_TO_WITH.finditer(text):
        token = match.group(1).lower()
        if token not in PERSON_STOP and token not in ORG_TAIL:
            found.add(token)
    for chunk in re.findall(
        r"\b[A-Z][a-z]{2,}(?:,\s+[A-Z][a-z]{2,})+,\s+and\s+[A-Z][a-z]{2,}\b",
        text,
    ):
        for part in re.findall(r"[A-Z][a-z]{2,}", chunk):
            if part.lower() not in PERSON_STOP and part.lower() not in ORG_TAIL:
                found.add(part.lower())
    return found


def extract_places(text: str | None) -> set[str]:
    if not text:
        return set()
    out: set[str] = set()
    for match in PLACE_RE.finditer(text):
        loc = re.sub(r"\s+", " ", match.group(0).lower())
        loc = loc.replace("st. george", "st george")
        out.add(loc)
    return out


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
    """Ingest already-filed titles (and optional summary body) as UNVERIFIED moves."""
    n = 0
    events = read_events(path)
    seen = {
        (e.get("recording_id"), e.get("folder_id"))
        for e in events
        if e.get("kind") == "move" and e.get("recording_id") and e.get("folder_id")
    }
    have_body = {
        e.get("recording_id")
        for e in events
        if e.get("kind") in ("move", "doc") and e.get("recording_id") and e.get("body")
    }
    for rec in recordings:
        fid = rec.get("folder_id")
        rid = rec.get("id") or rec.get("recording_id")
        title = rec.get("title") or rec.get("filename") or rec.get("new_name")
        headline = rec.get("headline")
        body = rec.get("body") or rec.get("summary")
        hour = rec.get("hour")
        if isinstance(body, str) and len(body) > 2000:
            body = body[:2000]
        if not fid or not rid:
            continue
        key = (rid, fid)
        if key not in seen:
            event = {
                "kind": "move",
                "action": "seen",
                "recording_id": rid,
                "folder_id": fid,
                "title": title,
            }
            if headline:
                event["headline"] = headline
            if body:
                event["body"] = body
            if isinstance(hour, int):
                event["hour"] = hour
            append(event, path=path)
            seen.add(key)
            if body:
                have_body.add(rid)
            n += 1
        elif body and rid not in have_body:
            doc = {
                "kind": "doc",
                "recording_id": rid,
                "folder_id": fid,
                "title": title,
                "headline": headline,
                "body": body,
            }
            if isinstance(hour, int):
                doc["hour"] = hour
            append(doc, path=path)
            have_body.add(rid)
            n += 1
    return n


def _folder_names(events: list[dict[str, Any]]) -> dict[str, str]:
    names: dict[str, str] = {}
    for e in events:
        fid, name = e.get("folder_id"), e.get("name")
        if isinstance(fid, str) and isinstance(name, str):
            names[fid] = name
    return names


def model_path(path: Path | None = None) -> Path:
    led = path or ledger_path()
    return led.with_name(led.stem + ".model.json")


def token_list(text: str | None) -> list[str]:
    out: list[str] = []
    for t in TOKEN.findall((text or "").lower()):
        if t in SKIP or t.isdigit() or re.fullmatch(r"20\d{2}", t):
            continue
        out.append(t)
    return out


def ngrams(text: str | None) -> Counter[str]:
    toks = token_list(text)
    counts: Counter[str] = Counter(toks)
    for a, b in zip(toks, toks[1:]):
        counts[f"{a} {b}"] += 1
    return counts


def entities(text: str | None) -> set[str]:
    """Proper nouns and hostnames from a summary. Not bag-of-words."""
    if not text:
        return set()
    out: set[str] = set()
    for match in PROPER.finditer(text):
        phrase = match.group(0).lower()
        parts = [p for p in re.split(r"[ -]", phrase) if p]
        if phrase in ENTITY_SKIP or phrase in SKIP:
            continue
        if any(p in ENTITY_SKIP for p in parts):
            continue
        if len(phrase) < 4:
            continue
        out.add(phrase)
    for host in HOST.findall(text.lower()):
        if host not in {"e.g", "i.e"} and "plaud.ai" not in host:
            out.add(host)
    return out


def _doc_text(event: dict[str, Any]) -> str:
    parts = [event.get("title"), event.get("headline"), event.get("body")]
    return "\n".join(p for p in parts if isinstance(p, str) and p.strip())


def _labeled_docs(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One labeled doc per recording_id (latest move/doc wins)."""
    by_id: dict[str, dict[str, Any]] = {}
    for e in events:
        if e.get("kind") not in ("move", "doc"):
            continue
        rid, fid = e.get("recording_id"), e.get("folder_id")
        if not isinstance(rid, str) or not isinstance(fid, str):
            continue
        prev = by_id.get(rid, {})
        by_id[rid] = {
            "recording_id": rid,
            "folder_id": fid,
            "title": e.get("title") or prev.get("title"),
            "headline": e.get("headline") or prev.get("headline"),
            "body": e.get("body") or prev.get("body"),
            "hour": e.get("hour") if e.get("hour") is not None else prev.get("hour"),
        }
    return list(by_id.values())


def fit(path: Path | None = None, *, persist: bool = True) -> dict[str, Any]:
    """Lift-weighted unigrams+bigrams from labeled filings. No sklearn."""
    events = read_events(path)
    names = _folder_names(events)
    docs = _labeled_docs(events)
    n_docs = len(docs)
    folder_n: Counter[str] = Counter()
    folder_tf: dict[str, Counter[str]] = defaultdict(Counter)
    folder_title_terms: dict[str, set[str]] = defaultdict(set)
    df: Counter[str] = Counter()
    for doc in docs:
        fid = str(doc["folder_id"])
        title_text = " ".join(p for p in (doc.get("title"), doc.get("headline")) if isinstance(p, str))
        title_grams = ngrams(title_text)
        ent = entities(str(doc.get("body") or "")) | entities(title_text)
        grams = title_grams + Counter(ent)
        if not grams:
            continue
        folder_n[fid] += 1
        folder_tf[fid] += grams
        folder_title_terms[fid].update(title_grams)
        df.update(set(grams))

    folders: dict[str, Any] = {}
    for fid, tf in folder_tf.items():
        n_f = max(folder_n[fid], 1)
        terms: dict[str, Any] = {}
        for term, count in tf.items():
            docs_with = df[term]
            p_f = count / n_f
            p_all = docs_with / max(n_docs, 1)
            lift = p_f / p_all if p_all else 0.0
            is_bigram = " " in term
            if docs_with == n_docs and not is_bigram:
                continue
            unique = docs_with == 1 and n_docs >= 2
            keep = count >= 2 or lift >= 3 or unique or (is_bigram and lift >= 2 and count >= 1)
            if n_f <= 2 and term not in folder_title_terms[fid] and " " not in term and "." not in term:
                keep = False
            if not is_bigram and term in GENERIC_UNIGRAMS:
                keep = False
            if is_bigram and term in GENERIC_PHRASES:
                keep = False
            if not keep:
                continue
            weight = round(math.log(1 + count) * min(lift, 25.0), 3)
            if weight < 0.6:
                continue
            terms[term] = {
                "count": int(count),
                "docs": int(docs_with),
                "lift": round(lift, 2),
                "weight": weight,
            }
        top = dict(sorted(terms.items(), key=lambda kv: -kv[1]["weight"])[:48])
        folders[fid] = {"name": names.get(fid), "n": int(folder_n[fid]), "terms": top}

    people_idx: dict[str, dict[str, int]] = defaultdict(Counter)
    places_idx: dict[str, dict[str, int]] = defaultdict(Counter)
    hours_idx: dict[str, dict[str, int]] = defaultdict(Counter)
    for doc in docs:
        fid = str(doc["folder_id"])
        text = _doc_text(doc)
        for person in extract_people(text):
            people_idx[person][fid] += 1
        for place in extract_places(text):
            places_idx[place][fid] += 1
        if isinstance(doc.get("hour"), int) and 0 <= int(doc["hour"]) <= 23:
            hours_idx[fid][str(int(doc["hour"]))] += 1

    model = {
        "version": 2,
        "algo": "people-place-time+lift",
        "fitted_at": int(time.time()),
        "n_docs": n_docs,
        "folders": folders,
        "people": {p: dict(c) for p, c in people_idx.items()},
        "places": {p: dict(c) for p, c in places_idx.items()},
        "hours": {fid: dict(c) for fid, c in hours_idx.items()},
        "confidence": "UNVERIFIED",
    }
    if persist:
        dest = model_path(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(model, indent=2), encoding="utf-8")
    return model


def load_model(path: Path | None = None) -> dict[str, Any] | None:
    dest = model_path(path)
    if not dest.is_file():
        return None
    try:
        obj = json.loads(dest.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def _folder_id_for(names: dict[str, str], *needles: str) -> str | None:
    for fid, name in names.items():
        n = (name or "").lower()
        if any(needle in n for needle in needles):
            return fid
    return None


BUILD_MARKERS = (
    "paseo",
    "prim",
    "plod",
    "aic hub",
    "entra",
    "railway",
    "eidos",
    "eidosh",
    "wrike",
    "canio",
    "board workers",
    "spreadsheet process",
)
ARP_OPS_STRONG = (
    "g702",
    "g703",
    "retainage",
    "lien waiver",
    "lender draw",
    "draw request",
)
GMW_OPS = (
    "cerebro.greenmarkwaste.com",
    "greenmarkwaste",
    "dd5",
    "cape citadel",
    "sage gl",
)


def hard_rule_build_vs_ops(title: str | None, body: str | None, names: dict[str, str]) -> dict[str, Any] | None:
    """Hard rule: building software → AIC; doing tenant ops → tenant folder.

    Not lift. Not optional. Still never auto-applies a move.
    """
    blob = f"{title or ''}\n{body or ''}".lower()
    if not blob.strip():
        return None
    aic = _folder_id_for(names, "aic")
    arp = _folder_id_for(names, "arp", "anthracite")
    gmw = _folder_id_for(names, "gmw", "greenmark")
    build = any(_term_in(m, blob) for m in BUILD_MARKERS)
    arp_ops = any(_term_in(m, blob) for m in ARP_OPS_STRONG)
    gmw_ops = any(_term_in(m, blob) for m in GMW_OPS)
    pay_app = _term_in("pay application", blob) or _term_in("pay app", blob)
    tenant_named = _term_in("anthracite", blob) or _term_in("arp", blob)

    if arp_ops and arp:
        return {
            "folder_id": arp,
            "name": names.get(arp),
            "reason": "tenant ops (pay app / draw / retainage / G702)",
        }
    if gmw_ops and gmw:
        return {
            "folder_id": gmw,
            "name": names.get(gmw),
            "reason": "Greenmark production / DD5 / Sage / cerebro.greenmarkwaste.com",
        }
    if build and aic:
        return {
            "folder_id": aic,
            "name": names.get(aic),
            "reason": "building software (Paseo / Prim / AIC Hub / railway), not tenant ops",
        }
    if tenant_named and aic and not arp_ops:
        if any(_term_in(m, blob) for m in ("spreadsheet", "dashboard", "railway", "web app")):
            return {
                "folder_id": aic,
                "name": names.get(aic),
                "reason": "tooling about a tenant is AIC Holdings, not the tenant folder",
            }
    if pay_app and not build and arp:
        return {
            "folder_id": arp,
            "name": names.get(arp),
            "reason": "pay application / draw work without a product-build marker",
        }
    return None


def _apply_hard_rule(
    folder_guess: list[dict[str, Any]],
    rule: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not rule or not rule.get("folder_id"):
        return folder_guess
    fid = rule["folder_id"]
    by_id = {g["folder_id"]: g for g in folder_guess}
    why = {"term": "hard_rule", "where": "build_vs_ops", "weight": 50, "reason": rule.get("reason")}
    if fid in by_id:
        by_id[fid]["score"] = round(max(float(by_id[fid]["score"]), 50.0) + 50.0, 3)
        by_id[fid].setdefault("why", []).insert(0, why)
        by_id[fid]["hard_rule"] = rule.get("reason")
    else:
        by_id[fid] = {
            "folder_id": fid,
            "name": rule.get("name"),
            "score": 50.0,
            "why": [why],
            "hard_rule": rule.get("reason"),
        }
    return sorted(by_id.values(), key=lambda r: -float(r["score"]))[:5]


def _unique_folder(dist: dict[str, Any]) -> str | None:
    positive = [fid for fid, n in dist.items() if int(n or 0) > 0]
    return positive[0] if len(positive) == 1 else None


def hour_from_recording(rec: dict[str, Any] | None) -> int | None:
    if not rec:
        return None
    if isinstance(rec.get("hour"), int) and 0 <= rec["hour"] <= 23:
        return rec["hour"]
    date = rec.get("date")
    if isinstance(date, str) and "T" in date:
        try:
            return int(date.split("T", 1)[1][:2])
        except ValueError:
            return None
    return None


def _score_people_place_time(
    model: dict[str, Any],
    title: str | None,
    body: str | None,
    hour: int | None,
    names: dict[str, str],
) -> dict[str, dict[str, Any]]:
    """Names, places, time-of-day. A person is not a folder — context is."""
    blob = f"{title or ''}\n{body or ''}"
    blob_l = blob.lower()
    scores: dict[str, dict[str, Any]] = defaultdict(lambda: {"score": 0.0, "why": []})
    people_map = model.get("people") or {}
    for person in extract_people(blob):
        dist = people_map.get(person) or {}
        if not dist and " " in person:
            dist = people_map.get(person.split()[0]) or {}
        if not dist:
            # unlabeled but family/home names in title still lean Personal
            personal = _folder_id_for(names, "personal")
            if personal and person in {"p-paw", "wyatt", "colleen", "angela", "sid", "jacob", "slate"}:
                scores[personal]["score"] += 12
                scores[personal]["why"].append({"term": person, "where": "person", "weight": 12})
            continue
        uniq = _unique_folder(dist)
        if uniq:
            scores[uniq]["score"] += 12
            scores[uniq]["why"].append({"term": person, "where": "person", "weight": 12})
            continue
        arp = _folder_id_for(names, "arp", "anthracite")
        aic = _folder_id_for(names, "aic")
        if arp and any(_term_in(m, blob_l) for m in ARP_OPS_STRONG):
            scores[arp]["score"] += 10
            scores[arp]["why"].append({"term": f"{person}+ops", "where": "person_context", "weight": 10})
        elif aic:
            scores[aic]["score"] += 6
            scores[aic]["why"].append({"term": f"{person}+work", "where": "person_context", "weight": 6})
        else:
            for fid, n in dist.items():
                scores[fid]["score"] += 3
                scores[fid]["why"].append({"term": person, "where": "person_shared", "weight": 3})
    places_map = model.get("places") or {}
    personal = _folder_id_for(names, "personal")
    homeish = {
        "home",
        "neighborhood",
        "zion",
        "vegas",
        "st george",
        "texas",
        "zion national park",
        "crested butte",
    }
    for place in extract_places(blob):
        dist = places_map.get(place) or {}
        uniq = _unique_folder(dist)
        if uniq:
            scores[uniq]["score"] += 10
            scores[uniq]["why"].append({"term": place, "where": "place", "weight": 10})
        elif personal and place in homeish:
            scores[personal]["score"] += 10
            scores[personal]["why"].append({"term": place, "where": "place", "weight": 10})
    if isinstance(hour, int) and 0 <= hour <= 23:
        hours = model.get("hours") or {}
        best_fid, best_n, total = None, 0, 0
        for fid, hist in hours.items():
            n = int(hist.get(str(hour), 0) or 0)
            total += n
            if n > best_n:
                best_fid, best_n = fid, n
        if best_fid and best_n >= 2 and total and best_n / total >= 0.5:
            scores[best_fid]["score"] += 3
            scores[best_fid]["why"].append({"term": f"hour:{hour:02d}", "where": "time", "weight": 3})
        title_l = (title or "").lower()
        if personal and (hour >= 18 or hour < 6) and "meeting:" not in title_l:
            if any(w in title_l for w in ("casual", "home", "reminder", "birthday", "neighborhood", "idea")):
                scores[personal]["score"] += 6
                scores[personal]["why"].append(
                    {"term": f"hour:{hour:02d}+offhours", "where": "time", "weight": 6}
                )
    return scores


def _alias_hits(events: list[dict[str, Any]], blob_text: str) -> Counter[str]:
    scores: Counter[str] = Counter()
    for e in events:
        if e.get("kind") != "note":
            continue
        fid = e.get("folder_id")
        terms = e.get("terms") if isinstance(e.get("terms"), list) else []
        if not isinstance(fid, str):
            continue
        hits = [t for t in terms if isinstance(t, str) and _term_in(t, blob_text)]
        if hits:
            scores[fid] += 4 * len(hits)
    return scores


def _score_text(model: dict[str, Any], title: str | None, body: str | None) -> list[dict[str, Any]]:
    title_l = (title or "").lower()
    body_l = (body or "").lower()
    blob = f"{title_l}\n{body_l}"
    ranked: list[dict[str, Any]] = []
    for fid, info in (model.get("folders") or {}).items():
        name = info.get("name")
        if _is_test_folder(name) and "probe" not in blob:
            continue
        score = 0.0
        why: list[dict[str, Any]] = []
        for term, meta in (info.get("terms") or {}).items():
            weight = float(meta.get("weight") or 0)
            in_title = _term_in(term, title_l)
            in_body = bool(body_l) and _term_in(term, body_l)
            strong = (" " in term) or ("." in term) or (len(term) >= 6 and weight >= 8)
            if in_title:
                hit = round(weight * (2 if strong else 1), 3)
                score += hit
                why.append({"term": term, "where": "title", "weight": hit})
            elif in_body and strong:
                hit = round(weight, 3)
                score += hit
                why.append({"term": term, "where": "body", "weight": hit})
        name_toks = tokens(str(name or ""))
        name_hit = sorted(name_toks & tokens(title))
        if name_hit:
            bonus = 3.0 * len(name_hit)
            score += bonus
            why.append({"term": " ".join(name_hit), "where": "folder_name", "weight": bonus})
        if score <= 0:
            continue
        why.sort(key=lambda w: -float(w["weight"]))
        ranked.append(
            {
                "folder_id": fid,
                "name": name,
                "score": round(score, 3),
                "why": why[:8],
            }
        )
    ranked.sort(key=lambda r: -r["score"])
    return ranked[:5]


def suggest(
    *,
    title: str | None = None,
    body: str | None = None,
    recording_id: str | None = None,
    hour: int | None = None,
    path: Path | None = None,
) -> dict[str, Any]:
    events = read_events(path)
    names = _folder_names(events)
    clock = is_clock_title(title)
    blob_text = f"{title or ''}\n{body or ''}".lower()
    empty_clock = clock and not (body or "").strip()

    model = load_model(path)
    led = path or ledger_path()
    if model is None or (led.is_file() and model_path(path).stat().st_mtime < led.stat().st_mtime):
        model = fit(path)

    folder_guess: list[dict[str, Any]] = []
    if not empty_clock:
        folder_guess = _score_text(model, title, body)
        aliases = _alias_hits(events, blob_text)
        by_id = {g["folder_id"]: g for g in folder_guess}
        for fid, bonus in aliases.items():
            if _is_test_folder(names.get(fid)) and "probe" not in blob_text:
                continue
            if fid in by_id:
                by_id[fid]["score"] = round(float(by_id[fid]["score"]) + bonus, 3)
                by_id[fid].setdefault("why", []).append(
                    {"term": "alias", "where": "note", "weight": bonus}
                )
            else:
                by_id[fid] = {
                    "folder_id": fid,
                    "name": names.get(fid),
                    "score": float(bonus),
                    "why": [{"term": "alias", "where": "note", "weight": bonus}],
                }
        ctx = _score_people_place_time(model, title, body, hour, names)
        ctx_max = 0.0
        for fid, hit in ctx.items():
            ctx_max = max(ctx_max, float(hit["score"]))
            if fid in by_id:
                by_id[fid]["score"] = round(float(by_id[fid]["score"]) + float(hit["score"]), 3)
                by_id[fid].setdefault("why", []).extend(hit["why"])
            else:
                by_id[fid] = {
                    "folder_id": fid,
                    "name": names.get(fid),
                    "score": float(hit["score"]),
                    "why": list(hit["why"]),
                }
        folder_guess = sorted(by_id.values(), key=lambda r: -float(r["score"]))[:5]
        # Product-noun rule is a tie-break only. People / place / time win.
        if ctx_max < 8:
            folder_guess = _apply_hard_rule(folder_guess, hard_rule_build_vs_ops(title, body, names))

    speakers: Counter[tuple[str, str]] = Counter()
    for e in events:
        if e.get("kind") == "rename_speaker" and e.get("original_label") and e.get("new_name"):
            speakers[(str(e["original_label"]), str(e["new_name"]))] += 1
    corrections: Counter[tuple[str, str, str]] = Counter()
    for e in events:
        if e.get("kind") == "correct" and e.get("find") and e.get("replace"):
            corrections[(str(e.get("target") or "transcript"), str(e["find"]), str(e["replace"]))] += 1

    speaker_guess = [
        {"original_label": a, "new_name": b, "count": n} for (a, b), n in speakers.most_common(8)
    ]
    correct_guess = [
        {"target": t, "find": f, "replace": r, "count": n} for (t, f, r), n in corrections.most_common(8)
    ]
    hard = bool(folder_guess and folder_guess[0].get("hard_rule"))
    weak = (not folder_guess or float(folder_guess[0]["score"]) < 2.0) and not hard
    return {
        "ok": True,
        "recording_id": recording_id,
        "title": title,
        "confidence": "UNVERIFIED",
        "do_not_apply": True,
        "algo": "people-place-time+lift",
        "hour": hour,
        "weak": weak,
        "folders": folder_guess,
        "speakers": speaker_guess,
        "corrections": correct_guess,
        "events": len(events),
        "n_docs": model.get("n_docs"),
        "clock_title": clock,
        "used_body": bool(body),
        "note": (
            "Clock title — do not guess a tenant from the timestamp."
            if empty_clock
            else "Guesses from a local lift model. Ask the human before mutate_recording."
        ),
    }


def cross_validate(path: Path | None = None) -> dict[str, Any]:
    """Leave-one-recording-out accuracy on labeled filings. Never applies moves."""
    events = read_events(path)
    names = _folder_names(events)
    docs = _labeled_docs(events)
    rows: list[dict[str, Any]] = []
    hits = 0
    for held in docs:
        rest_events = [
            e
            for e in events
            if not (e.get("kind") in ("move", "doc") and e.get("recording_id") == held["recording_id"])
        ]
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as fh:
            for e in rest_events:
                fh.write(json.dumps(e) + "\n")
            tmp = Path(fh.name)
        try:
            fit(tmp, persist=True)
            guess = suggest(
                title=held.get("title"),
                body=held.get("body"),
                hour=held.get("hour") if isinstance(held.get("hour"), int) else None,
                path=tmp,
            )
        finally:
            tmp.unlink(missing_ok=True)
            tmp.with_name(tmp.stem + ".model.json").unlink(missing_ok=True)
        top = guess["folders"][0]["folder_id"] if guess["folders"] else None
        weak = bool(guess.get("weak"))
        ok = top == held["folder_id"] and not weak
        if ok:
            hits += 1
        rows.append(
            {
                "recording_id": held["recording_id"],
                "title": held.get("title"),
                "actual": names.get(str(held["folder_id"]), held["folder_id"]),
                "guess": names.get(str(top), top) if top else None,
                "ok": ok,
                "abstain": weak or not top,
                "score": guess["folders"][0]["score"] if guess["folders"] else 0,
            }
        )
    n = len(docs)
    abstain = sum(1 for r in rows if r["abstain"])
    wrong = sum(1 for r in rows if not r["ok"] and not r["abstain"])
    return {
        "ok": True,
        "algo": "lift-ngrams",
        "n": n,
        "hits": hits,
        "wrong": wrong,
        "abstain": abstain,
        "accuracy": round(hits / n, 3) if n else 0,
        "confidence": "UNVERIFIED",
        "do_not_apply": True,
        "rows": rows,
    }


def status(path: Path | None = None) -> dict[str, Any]:
    events = read_events(path)
    kinds = Counter(str(e.get("kind") or "unknown") for e in events)
    model = load_model(path)
    folder_terms = {
        (info.get("name") or fid): len(info.get("terms") or {})
        for fid, info in ((model or {}).get("folders") or {}).items()
    }
    return {
        "ok": True,
        "path": str(path or ledger_path()),
        "events": len(events),
        "kinds": dict(kinds),
        "model": {
            "algo": (model or {}).get("algo"),
            "n_docs": (model or {}).get("n_docs"),
            "term_counts": folder_terms,
        }
        if model
        else None,
        "confidence": "UNVERIFIED",
        "note": "Operational ledger, not lessons.md. CONFIRMED is illegal here.",
    }


def recall(*, kind: str | None = None, limit: int = 20, path: Path | None = None) -> dict[str, Any]:
    events = read_events(path)
    if kind:
        events = [e for e in events if e.get("kind") == kind]
    return {"ok": True, "events": events[-limit:], "count": len(events)}


def rank(recordings: list[dict[str, Any]], path: Path | None = None) -> dict[str, Any]:
    """Score many recordings. Never moves them."""
    rows: list[dict[str, Any]] = []
    for rec in recordings:
        title = rec.get("title") or rec.get("filename")
        guess = suggest(
            title=title,
            body=rec.get("body") or rec.get("summary"),
            recording_id=rec.get("id") or rec.get("recording_id"),
            hour=hour_from_recording(rec),
            path=path,
        )
        top = guess["folders"][0] if guess["folders"] else None
        rows.append(
            {
                "id": rec.get("id") or rec.get("recording_id"),
                "title": title,
                "guess": (top or {}).get("name"),
                "folder_id": (top or {}).get("folder_id"),
                "score": (top or {}).get("score") or 0,
                "weak": guess.get("weak"),
                "clock_title": guess.get("clock_title"),
                "why": (top or {}).get("why") or [],
            }
        )
    return {"ok": True, "do_not_apply": True, "algo": "lift-ngrams", "n": len(rows), "rows": rows}
