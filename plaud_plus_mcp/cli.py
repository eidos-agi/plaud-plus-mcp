"""plaud-plus CLI: login / doctor, then pass through to plaud-tools."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

from . import __version__
from .auth import AuthError, desktop_available, ensure_session, keyring_get, seed_wrt_from_desktop
from .learn import (
    cross_validate,
    fit,
    hour_from_recording,
    rank,
    recall,
    remember,
    snapshot_filings,
    snapshot_folders,
    status,
    suggest,
)


def _print_json(value: object) -> None:
    json.dump(value, sys.stdout, indent=2)
    sys.stdout.write("\n")


def cmd_login(args: argparse.Namespace) -> int:
    if args.desktop:
        if not desktop_available():
            print("plaud-plus: Plaud Desktop encryption.json not found", file=sys.stderr)
            return 2
        try:
            seed_wrt_from_desktop()
            source = ensure_session()
        except AuthError as exc:
            print(f"plaud-plus: {exc}", file=sys.stderr)
            return 2
        _print_json({"ok": True, "method": "desktop", "session": source})
        return 0

    if not args.email:
        print("plaud-plus: pass --email or --desktop", file=sys.stderr)
        return 2
    cmd = ["plaud-tools", "login", "--email", args.email, "--region", args.region]
    return subprocess.call(cmd)


def cmd_doctor(_args: argparse.Namespace) -> int:
    try:
        source = ensure_session()
    except AuthError as exc:
        _print_json({"ok": False, "error": str(exc), "has_wrt": bool(keyring_get())})
        return 2
    ping = subprocess.run(["plaud-tools", "ping"], capture_output=True, text=True)
    body: dict = {"ok": ping.returncode == 0, "session": source, "version": __version__}
    try:
        body["ping"] = json.loads(ping.stdout or "{}")
    except json.JSONDecodeError:
        body["ping_raw"] = (ping.stdout or ping.stderr or "")[:400]
    _print_json(body)
    return ping.returncode


def _client():
    from plaud_tools.core.client import PlaudClient
    from plaud_tools.core.session import SessionManager, SessionStore

    return PlaudClient(SessionManager(SessionStore()))


def _filed_docs_with_summaries() -> tuple[list[dict], list[dict]]:
    from plaud_tools.core.client import PlaudRecordingQuery

    client = _client()
    folders = [{"id": t.id, "name": t.name, "color": t.color} for t in client.list_file_tags()]
    recs = []
    skip = 0
    while True:
        batch = client.list_recordings(
            PlaudRecordingQuery(skip=skip, limit=200, is_trash=0, sort_by="start_time", is_desc=True)
        )
        if not batch:
            break
        recs.extend(batch)
        if len(batch) < 200:
            break
        skip += 200
    filed = [r for r in recs if r.filetag_id_list]
    docs = []
    for i, r in enumerate(filed, 1):
        print(f"plaud-plus: summary {i}/{len(filed)} {r.filename[:60]}", file=sys.stderr)
        detail = client.get_recording(r.id, include_summary=True)
        extra = detail.extra_data or {}
        headline = (extra.get("aiContentHeader") or {}).get("headline")
        body = detail.ai_content if isinstance(detail.ai_content, str) else None
        from datetime import datetime as _dt

        hour = None
        try:
            hour = _dt.fromtimestamp(r.start_time / 1000).hour
        except Exception:
            hour = None
        docs.append(
            {
                "id": r.id,
                "folder_id": r.filetag_id_list[0],
                "title": r.filename,
                "headline": headline,
                "body": body,
                "hour": hour,
            }
        )
    return folders, docs


def cmd_train(args: argparse.Namespace) -> int:
    from .train import serve

    try:
        ensure_session()
    except AuthError as exc:
        print(f"plaud-plus: {exc}", file=sys.stderr)
        return 2
    return serve(host=args.host, port=args.port, open_browser=not args.no_open)


def cmd_learn(args: argparse.Namespace) -> int:
    action = args.action or "status"
    if action == "status":
        _print_json(status())
        return 0
    if action == "recall":
        _print_json(recall(kind=args.kind, limit=args.limit))
        return 0
    if action == "remember":
        if not args.claim:
            print("plaud-plus: learn remember needs --claim", file=sys.stderr)
            return 2
        _print_json(remember(args.claim))
        return 0
    if action == "snapshot":
        try:
            ensure_session()
        except AuthError as exc:
            print(f"plaud-plus: {exc}", file=sys.stderr)
            return 2
        folders, docs = _filed_docs_with_summaries()
        n_folders = snapshot_folders(folders)
        n_filed = snapshot_filings(docs)
        model = fit()
        _print_json(
            {
                "ok": True,
                "ingested_folders": n_folders,
                "ingested_filings": n_filed,
                "model": {"n_docs": model.get("n_docs"), "folders": {v.get("name"): v.get("n") for v in (model.get("folders") or {}).values()}},
                **status(),
            }
        )
        return 0
    if action == "fit":
        model = fit()
        _print_json(
            {
                "ok": True,
                "n_docs": model.get("n_docs"),
                "folders": {
                    (info.get("name") or fid): {
                        "n": info.get("n"),
                        "top": list((info.get("terms") or {}).keys())[:12],
                    }
                    for fid, info in (model.get("folders") or {}).items()
                },
                "confidence": "UNVERIFIED",
                "do_not_apply": True,
            }
        )
        return 0
    if action == "cv":
        _print_json(cross_validate())
        return 0
    if action == "rank":
        try:
            ensure_session()
        except AuthError as exc:
            print(f"plaud-plus: {exc}", file=sys.stderr)
            return 2
        listed = subprocess.run(
            ["plaud-tools", "list", "--unfiled", "--limit", "200"],
            capture_output=True,
            text=True,
        )
        if listed.returncode != 0:
            print(listed.stderr or listed.stdout, file=sys.stderr)
            return listed.returncode
        try:
            recs = json.loads(listed.stdout)
        except json.JSONDecodeError:
            print("plaud-plus: list was not JSON", file=sys.stderr)
            return 2
        _print_json(rank(recs if isinstance(recs, list) else []))
        return 0
    if action == "suggest":
        title = args.title
        body = None
        hour = None
        rid = args.recording_id
        if rid:
            try:
                ensure_session()
            except AuthError as exc:
                print(f"plaud-plus: {exc}", file=sys.stderr)
                return 2
            shown = subprocess.run(
                ["plaud-tools", "summary", rid],
                capture_output=True,
                text=True,
            )
            if shown.returncode == 0:
                try:
                    payload = json.loads(shown.stdout)
                except json.JSONDecodeError:
                    payload = {}
                raw = payload.get("summary") if isinstance(payload, dict) else None
                if isinstance(raw, str) and raw.strip():
                    body = raw
            shown = subprocess.run(
                ["plaud-tools", "show", rid],
                capture_output=True,
                text=True,
            )
            if shown.returncode == 0:
                try:
                    payload = json.loads(shown.stdout)
                except json.JSONDecodeError:
                    payload = {}
                if isinstance(payload, dict):
                    if not title:
                        title = payload.get("title") or payload.get("filename") or title
                    hour = hour_from_recording(payload)
        _print_json(suggest(title=title, body=body, recording_id=rid, hour=hour))
        return 0
    print(f"plaud-plus: unknown learn action {action}", file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    ours = {"login", "doctor", "learn", "train", "-h", "--help", "--version"}
    if not argv or argv[0] in ours:
        parser = argparse.ArgumentParser(
            prog="plaud-plus",
            description="Write-capable Plaud CLI / MCP (web API). Unofficial.",
        )
        parser.add_argument("--version", action="version", version=f"plaud-plus {__version__}")
        sub = parser.add_subparsers(dest="cmd")

        login = sub.add_parser("login", help="Sign in (email/password or Plaud Desktop on macOS)")
        login.add_argument("--email")
        login.add_argument("--region", choices=["us", "eu"], default="us")
        login.add_argument(
            "--desktop",
            action="store_true",
            help="Seed from a signed-in Plaud Desktop app (macOS, Google SSO)",
        )
        login.set_defaults(func=cmd_login)

        doctor = sub.add_parser("doctor", help="Refresh session and ping Plaud")
        doctor.set_defaults(func=cmd_doctor)

        learn = sub.add_parser("learn", help="Local UNVERIFIED observations from writes")
        learn.add_argument(
            "action",
            nargs="?",
            default="status",
            choices=["status", "recall", "suggest", "remember", "snapshot", "fit", "cv", "rank"],
        )
        learn.add_argument("--title")
        learn.add_argument("--recording-id")
        learn.add_argument("--claim")
        learn.add_argument("--kind")
        learn.add_argument("--limit", type=int, default=20)
        learn.set_defaults(func=cmd_learn)

        train = sub.add_parser("train", help="Local HITL UI to file recordings and refit the model")
        train.add_argument("--port", type=int, default=7843)
        train.add_argument("--host", default="127.0.0.1")
        train.add_argument("--no-open", action="store_true")
        train.set_defaults(func=cmd_train)

        args = parser.parse_args(argv)
        if not args.cmd:
            parser.print_help()
            return 0
        return int(args.func(args))

    try:
        ensure_session()
    except AuthError as exc:
        print(f"plaud-plus: {exc}", file=sys.stderr)
        return 2
    return subprocess.call(["plaud-tools", *argv])


if __name__ == "__main__":
    raise SystemExit(main())
