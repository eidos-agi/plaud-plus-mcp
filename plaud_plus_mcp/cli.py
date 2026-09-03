"""plaud-plus CLI: login / doctor, then pass through to plaud-tools."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

from . import __version__
from .auth import AuthError, desktop_available, ensure_session, keyring_get, seed_wrt_from_desktop


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


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    ours = {"login", "doctor", "-h", "--help", "--version"}
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
