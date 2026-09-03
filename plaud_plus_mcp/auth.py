"""Session bootstrap for Plaud Plus.

Official @plaud-ai/mcp uses developer OAuth and cannot write.
Plaud Plus uses the same web API the site and Plaud Desktop use.

Two ways in:

1. Email + password via ``plaud-tools login`` (30-day tokens).
2. macOS Plaud Desktop seed (Google SSO users): read the workspace
   refresh token Desktop already has, then mint a 24h workspace token.
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

KR_SERVICE = "plaud-plus"
KR_ACCOUNT = "wrt"

ENC_PATH = Path.home() / "Library/Application Support/Plaud/encryption.json"
CFG_PATH = Path.home() / "Library/Application Support/Plaud/config.json"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/136.0.0.0 Safari/537.36"
)

# Workspace tokens last ~24h. plaud-tools refuses anything inside a 24h
# buffer, which makes a fresh WT unusable. 15 minutes still refuses a
# token that is about to die.
TOKEN_REFRESH_BUFFER_SECONDS = 15 * 60


class AuthError(RuntimeError):
    """User-facing auth failure (no secrets in the message)."""


def patch_plaud_tools_buffer() -> None:
    import plaud_tools.core.session as session_mod

    session_mod.TOKEN_REFRESH_BUFFER_SECONDS = TOKEN_REFRESH_BUFFER_SECONDS


def decode_jwt_payload(token: str) -> dict[str, Any] | None:
    parts = token.split(".")
    if len(parts) != 3:
        return None
    segment = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        obj = json.loads(base64.urlsafe_b64decode(segment.encode("ascii")))
    except (ValueError, json.JSONDecodeError):
        return None
    return obj if isinstance(obj, dict) else None


def region_from_payload(payload: dict[str, Any] | None, default: str = "us") -> str:
    if not payload:
        return default
    raw = str(payload.get("region") or default).lower()
    if raw.startswith("eu"):
        return "eu"
    return "us"


def api_base(region: str) -> str:
    from plaud_tools.core.models import BASE_URLS

    return BASE_URLS.get(region, BASE_URLS["us"])


def workspace_id_from_wrt(wrt: str) -> str | None:
    payload = decode_jwt_payload(wrt)
    if not payload:
        return None
    wid = payload.get("wid")
    return str(wid) if wid else None


def email_from_me(me: dict[str, Any]) -> str | None:
    user = me.get("data_user") if isinstance(me.get("data_user"), dict) else {}
    for key in ("email", "user_email", "mail"):
        val = user.get(key) or me.get(key)
        if isinstance(val, str) and "@" in val:
            return val
    return None


def derive_chrome_os_crypt_key(password: bytes) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA1(), length=16, salt=b"saltysalt", iterations=1003)
    return kdf.derive(password)


def decrypt_safe_storage_v10(b64: str, key: bytes) -> str:
    blob = base64.b64decode(b64)
    if not blob.startswith(b"v10"):
        raise AuthError("Plaud Desktop token is not a v10 safeStorage blob")
    pt = Cipher(algorithms.AES(key), modes.CBC(b" " * 16)).decryptor()
    out = pt.update(blob[3:]) + pt.finalize()
    pad = out[-1]
    if 1 <= pad <= 16:
        out = out[:-pad]
    return out.decode("utf-8")


def keyring_get() -> str | None:
    import keyring

    val = keyring.get_password(KR_SERVICE, KR_ACCOUNT)
    return val or None


def keyring_set(value: str) -> None:
    import keyring

    keyring.set_password(KR_SERVICE, KR_ACCOUNT, value)


def macos_safe_storage_password() -> bytes:
    r = subprocess.run(
        [
            "security",
            "find-generic-password",
            "-w",
            "-s",
            "Plaud Safe Storage",
            "-a",
            "Plaud Key",
        ],
        capture_output=True,
        check=False,
    )
    if r.returncode != 0:
        raise AuthError("could not read Plaud Safe Storage from the macOS keychain")
    return (r.stdout or b"").strip()


def desktop_available() -> bool:
    return ENC_PATH.is_file()


def seed_wrt_from_desktop() -> str:
    if not ENC_PATH.is_file():
        raise AuthError("Plaud Desktop encryption.json not found")
    enc = json.loads(ENC_PATH.read_text())
    raw = enc.get("wrtToken")
    if not isinstance(raw, str) or len(raw) < 20:
        raise AuthError("Plaud Desktop has no workspace refresh token")
    key = derive_chrome_os_crypt_key(macos_safe_storage_password())
    wrt = decrypt_safe_storage_v10(raw, key)
    keyring_set(wrt)
    return wrt


def workspace_id() -> str:
    env = os.getenv("PLAUD_WORKSPACE_ID")
    if env:
        return env
    if CFG_PATH.is_file():
        cfg = json.loads(CFG_PATH.read_text())
        ws = cfg.get("currentWorkspaceId")
        if isinstance(ws, str) and ws:
            return ws
    wrt = keyring_get()
    if wrt:
        wid = workspace_id_from_wrt(wrt)
        if wid:
            return wid
    raise AuthError("no Plaud workspace id (set PLAUD_WORKSPACE_ID or sign in via Desktop)")


def _request_json(method: str, url: str, token: str, body: bytes | None = None) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": UA,
            "app-platform": "web",
            "edit-from": "web",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        raise AuthError(f"Plaud HTTP {exc.code} on {method} {url.split('plaud.ai', 1)[-1]}") from exc
    except urllib.error.URLError as exc:
        raise AuthError("could not reach Plaud API") from exc
    if not isinstance(payload, dict):
        raise AuthError("Plaud returned a non-object JSON payload")
    return payload


def refresh_workspace(wrt: str, *, ws_id: str | None = None, region: str | None = None) -> dict[str, Any]:
    payload_jwt = decode_jwt_payload(wrt)
    region = region or region_from_payload(payload_jwt)
    ws_id = ws_id or workspace_id_from_wrt(wrt) or workspace_id()
    url = f"{api_base(region)}/user-app/auth/workspace/refresh/{ws_id}"
    payload = _request_json("POST", url, wrt, body=b"{}")
    if payload.get("status") != 0 or not isinstance(payload.get("data"), dict):
        raise AuthError(
            f"workspace refresh failed status={payload.get('status')} msg={payload.get('msg')}"
        )
    data = payload["data"]
    wt = data.get("workspace_token") or data.get("access_token")
    if not isinstance(wt, str) or not wt:
        raise AuthError("refresh response had no workspace_token")
    new_wrt = data.get("refresh_token")
    if isinstance(new_wrt, str) and new_wrt and new_wrt != wrt:
        keyring_set(new_wrt)
    me = _request_json("GET", f"{api_base(region)}/user/me", wt)
    email = email_from_me(me)
    from plaud_tools.core.session import PlaudSession, SessionStore

    SessionStore().save(PlaudSession(access_token=wt, region=region, email=email))
    return {"ok": True, "region": region, "has_email": bool(email), "workspace_id": ws_id}


def existing_plaud_tools_session_ok() -> bool:
    from plaud_tools.core.session import SessionManager, SessionStore

    try:
        SessionManager(SessionStore()).require()
    except Exception:
        return False
    return True


def ensure_session() -> str:
    """Make a usable plaud-tools session. Returns the source used."""
    patch_plaud_tools_buffer()
    wrt = keyring_get()
    if wrt:
        try:
            refresh_workspace(wrt)
            return "workspace_refresh"
        except AuthError:
            if desktop_available():
                wrt = seed_wrt_from_desktop()
                refresh_workspace(wrt)
                return "desktop_reseed"
            raise
    if existing_plaud_tools_session_ok():
        return "plaud_tools_session"
    if desktop_available():
        wrt = seed_wrt_from_desktop()
        refresh_workspace(wrt)
        return "desktop_seed"
    raise AuthError(
        "No Plaud session. Run `plaud-plus login --email you@example.com` "
        "or `plaud-plus login --desktop` on macOS with Plaud Desktop signed in."
    )
