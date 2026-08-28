"""
Authentication via streamlit-authenticator.

Credentials (bcrypt-hashed passwords) and cookie settings come from Streamlit
secrets — see `.streamlit/secrets.toml`. The signed browser cookie
(`cookie_expiry_days`, default 30) is what keeps the same machine logged in
without re-prompting.

`require_login()` is called once, by `app.py`, before routing. Individual pages
call `current_user()`, which only reads the already-populated session state.
"""

from __future__ import annotations

import streamlit as st
import streamlit_authenticator as stauth

from lib.config import admin_users, config_problem, cookie_config, credentials


def get_authenticator() -> stauth.Authenticate:
    # Not cached: Authenticate touches a Streamlit component (the cookie
    # manager) on construction, which is incompatible with st.cache_*. It is
    # cheap to build and is meant to be re-created each rerun.
    cookie = cookie_config()
    return stauth.Authenticate(
        credentials(),
        cookie["name"],
        cookie["key"],
        cookie["expiry_days"],
    )


def current_user() -> dict:
    """Read the authenticated user from session state (set by require_login)."""
    username = st.session_state.get("username")
    return {
        "username": username,
        "name": st.session_state.get("name") or username,
        "is_admin": username in admin_users(),
    }


def require_login() -> dict:
    """
    Render the login form and stop the script unless the user is authenticated.
    Returns the `current_user()` dict plus the authenticator instance.
    """
    problem = config_problem()
    if problem:
        st.error(f"Login is not configured correctly.\n\n{problem}")
        st.stop()

    authenticator = get_authenticator()
    authenticator.login(location="main")

    status = st.session_state.get("authentication_status")
    if status is None:
        st.info("Please log in to continue.")
        st.stop()
    if status is False:
        st.error("Username or password is incorrect.")
        st.stop()

    return {**current_user(), "authenticator": authenticator}
