from __future__ import annotations

import base64
import json

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from plaud_plus_mcp.auth import (
    decode_jwt_payload,
    decrypt_safe_storage_v10,
    derive_chrome_os_crypt_key,
    email_from_me,
    region_from_payload,
    workspace_id_from_wrt,
)


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _jwt(payload: dict) -> str:
    hdr = _b64url(json.dumps({"alg": "none", "typ": "JWT"}).encode())
    body = _b64url(json.dumps(payload).encode())
    return f"{hdr}.{body}.sig"


def test_decode_workspace_id_and_region() -> None:
    token = _jwt({"wid": "ws_abc", "region": "us-east", "exp": 9_999_999_999})
    assert workspace_id_from_wrt(token) == "ws_abc"
    assert region_from_payload(decode_jwt_payload(token)) == "us"


def test_eu_region() -> None:
    token = _jwt({"wid": "ws_eu", "region": "eu-central"})
    assert region_from_payload(decode_jwt_payload(token)) == "eu"


def test_email_from_me() -> None:
    me = {"status": 0, "data_user": {"email": "a@example.com", "nickname": "A"}}
    assert email_from_me(me) == "a@example.com"
    assert email_from_me({"status": 0}) is None


def test_safe_storage_roundtrip() -> None:
    password = b"unit-test-password"
    key = derive_chrome_os_crypt_key(password)
    plain = "wrt-token-value"
    data = plain.encode()
    pad = 16 - (len(data) % 16)
    data = data + bytes([pad]) * pad
    ct = Cipher(algorithms.AES(key), modes.CBC(b" " * 16)).encryptor()
    blob = b"v10" + ct.update(data) + ct.finalize()
    b64 = base64.b64encode(blob).decode("ascii")
    assert decrypt_safe_storage_v10(b64, key) == plain


def test_malformed_jwt() -> None:
    assert decode_jwt_payload("not-a-jwt") is None
    assert workspace_id_from_wrt("nope") is None
