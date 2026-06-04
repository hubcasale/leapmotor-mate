"""Optional standalone authentication.

A single shared password (env MATE_AUTH_PASSWORD) gates the whole UI when Mate runs
as standalone Docker exposed beyond localhost. It is intentionally a NO-OP when
running as a Home Assistant add-on: there the Supervisor ingress already authenticates
every request, so a second login would just get in the way (and break ingress).

The session is a Fernet token (signed + encrypted with the same per-install key as the
credential encryption, /data/secret.key) carried in an HttpOnly, SameSite=Strict cookie
— so it survives restarts, can't be read by JS, and isn't sent on cross-site requests
(a solid CSRF defense for the authenticated app).
"""
import hmac
import os

from cryptography.fernet import Fernet, InvalidToken

import crypto

COOKIE = "mate_session"
TTL = 30 * 86400          # 30 days
_MARK = b"mate-auth-v1"
_fernet = None


def _f() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = Fernet(crypto.load_or_create_key())
    return _fernet


def password() -> str:
    return os.environ.get("MATE_AUTH_PASSWORD", "")


def enabled() -> bool:
    """On only for standalone with a password set. Add-on mode (Supervisor ingress
    already authenticates) is always exempt."""
    if os.environ.get("SUPERVISOR_TOKEN") or os.environ.get("HASSIO_TOKEN"):
        return False
    return bool(password())


def check_password(pw: str) -> bool:
    return bool(pw) and hmac.compare_digest(pw, password())


def make_token() -> str:
    return _f().encrypt(_MARK).decode()


def valid(token: str) -> bool:
    if not token:
        return False
    try:
        return _f().decrypt(token.encode(), ttl=TTL) == _MARK
    except (InvalidToken, Exception):  # noqa: BLE001
        return False
