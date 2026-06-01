"""Shared Leapmotor session between the poller and the web process.

Both run in the same container with the same account + device_id + cert, so two
independent logins evict each other (Leapmotor allows one session per device). Here
the auth state (token + sign material + account-cert file paths) is persisted to the
DB (settings['shared_session']) and `api.login` is monkey-patched to RESTORE that
shared token before ever doing a real login. The pip client's internal token-expiry
retry also calls api.login, so this intercepts every login path.

Fully defensive: any failure falls back to a normal login — the app never breaks.
"""
import json
import logging
import os
import sqlite3
import time
import types

log = logging.getLogger("session_share")

_TTL = 45 * 60   # only restore a session blob younger than this (token lifetime margin)
_GUARD_S = 10    # don't re-attempt restore within this window (breaks retry recursion)

_ATTRS = ("user_id", "token", "refresh_token", "device_id",
          "sign_ikm", "sign_salt", "sign_info", "account_cert_file", "account_key_file")


def _db_path() -> str:
    return os.environ.get("DB_PATH", "leapmotor_mate.db")


def _save(api) -> None:
    try:
        blob = {a: getattr(api, a, None) for a in _ATTRS}
        blob["ts"] = time.time()
        c = sqlite3.connect(_db_path(), timeout=5)
        c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('shared_session', ?)",
                  (json.dumps(blob),))
        c.commit()
        c.close()
    except Exception as e:  # noqa: BLE001
        log.debug("shared session save failed: %s", e)


def _restore(api) -> bool:
    try:
        c = sqlite3.connect(_db_path(), timeout=5)
        row = c.execute("SELECT value FROM settings WHERE key='shared_session'").fetchone()
        c.close()
        if not row:
            return False
        b = json.loads(row[0])
    except Exception:  # noqa: BLE001
        return False
    if not b.get("token") or time.time() - b.get("ts", 0) > _TTL:
        return False
    acf, akf = b.get("account_cert_file"), b.get("account_key_file")
    if not acf or not akf or not os.path.exists(acf) or not os.path.exists(akf):
        return False
    try:
        for a in _ATTRS:
            setattr(api, a, b.get(a))
        api.remote_cert_synced = False
        return True
    except Exception:  # noqa: BLE001
        return False


def _shared_login(self) -> None:
    """Replacement for api.login: restore the shared token first; do a real login only
    when there is no recent shared session (or a just-restored one failed within the
    guard window). After a real login, persist the new session for the other process."""
    if time.time() - getattr(self, "_mate_restore_at", 0) > _GUARD_S:
        self._mate_restore_at = time.time()
        if _restore(self):
            log.info("Reusing shared session token (no login)")
            return
    type(self).login(self)   # original, unpatched class login
    _save(self)
    log.info("New login — shared session saved")


def _shared_token_refresh(self) -> None:
    """Persist the refreshed token too, so the other process picks it up."""
    type(self).token_refresh(self)
    _save(self)


def install(api):
    """Route every login / token-refresh through the shared-session logic."""
    try:
        api.login = types.MethodType(_shared_login, api)
        api.token_refresh = types.MethodType(_shared_token_refresh, api)
    except Exception as e:  # noqa: BLE001
        log.warning("Could not install shared session: %s", e)
    return api
