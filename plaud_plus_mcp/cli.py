"""plaud-plus CLI: login / doctor, then pass through to plaud-tools."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

from . import __version__
from .auth import AuthError, desktop_available, ensure_session, keyring_get, seed_wrt_from_desktop
from .learn import recall, remember, snapshot_folders, status, suggest


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
        listed = subprocess.run(["plaud-tools", "folders"], capture_output=True, text=True)
        if listed.returncode != 0:
            print(listed.stderr or listed.stdout, file=sys.stderr)
            return listed.returncode
        try:
            folders = json.loads(listed.stdout)
        except json.JSONDecodeError:
            print("plaud-plus: folders was not JSON", file=sys.stderr)
            return 2
        n = snapshot_folders(folders if isinstance(folders, list) else [])
        _print_json({"ok": True, "ingested": n, **status()})
        return 0
    if action == "suggest":
        _print_json(suggest(title=args.title, recording_id=args.recording_id))
        return 0
    print(f"plaud-plus: unknown learn action {action}", file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    ours = {"login", "doctor", "learn", "-h", "--help", "--version"}
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
            choices=["status", "recall", "suggest", "remember", "snapshot"],
        )
        learn.add_argument("--title")
        learn.add_argument("--recording-id")
        learn.add_argument("--claim")
        learn.add_argument("--kind")
        learn.add_argument("--limit", type=int, default=20)
        learn.set_defaults(func=cmd_learn)

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
