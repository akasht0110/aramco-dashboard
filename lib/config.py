"""
Central configuration.

Values come from (in order of precedence):
  1. Environment variables  -- used by the CLI (`import_data.py`) and CI.
  2. Streamlit secrets       -- used when running inside `streamlit run`.
  3. Built-in defaults.

This lets the same code target a local SQLite file during development and a
hosted Postgres database (Neon) in production without any code change.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any


def _secrets() -> Any:
    """Return st.secrets if available, else an empty dict-like object."""
    try:
        import streamlit as st

        return st.secrets
    except Exception:
        return {}


def _get(section: str, key: str, env: str, default: Any = None) -> Any:
    if env in os.environ:
        return os.environ[env]
    sec = _secrets()
    try:
        if section in sec and key in sec[section]:
            return sec[section][key]
    except Exception:
        pass
    return default


@lru_cache(maxsize=1)
def database_url() -> str:
    """
    SQLAlchemy database URL.

    Local default: a SQLite file (`aramco.db`) in the project root.
    Production: set `DATABASE_URL` env var or `[db].url` in Streamlit secrets to
    a Postgres URL, e.g.
        postgresql+psycopg2://user:pass@host/dbname?sslmode=require
    """
    return _get("db", "url", "DATABASE_URL", "sqlite:///aramco.db")


def cookie_config() -> dict:
    return {
        "name": _get("auth", "cookie_name", "AUTH_COOKIE_NAME", "aramco_dashboard_auth"),
        "key": _get("auth", "cookie_key", "AUTH_COOKIE_KEY", "change-me"),
        "expiry_days": float(
            _get("auth", "cookie_expiry_days", "AUTH_COOKIE_EXPIRY_DAYS", 30)
        ),
    }


def admin_users() -> list[str]:
    sec = _secrets()
    try:
        users = sec["auth"]["admin_users"]
        return list(users)
    except Exception:
        return ["admin"]


def credentials() -> dict:
    """
    Credentials dict in the shape streamlit-authenticator expects:
        {"usernames": {"<user>": {"name": ..., "email": ..., "password": <hash>}}}
    """
    sec = _secrets()
    try:
        auth = sec["auth"]
    except Exception:
        return {"usernames": {}}
    if "credentials" not in auth:
        return {"usernames": {}}
    # st.secrets returns an AttrDict; convert to plain dict recursively.
    return _to_plain(auth["credentials"])


def config_problem() -> str | None:
    """
    Returns a human-readable reason the auth config is unusable, or None if OK.
    Used to show a clear message instead of silently rejecting every login.
    """
    if not _secrets():
        return "No secrets found. Add the [auth] block in the app's Settings → Secrets."
    creds = credentials()
    users = creds.get("usernames") or {}
    if not users:
        return (
            "Auth config is missing or malformed: no accounts found under "
            "[auth.credentials.usernames] in the app secrets."
        )
    missing = [u for u, v in users.items() if not (v or {}).get("password")]
    if missing:
        return f"These accounts have no password hash in secrets: {', '.join(missing)}."
    return None


def _to_plain(obj: Any) -> Any:
    if hasattr(obj, "items"):
        return {k: _to_plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_plain(v) for v in obj]
    return obj
