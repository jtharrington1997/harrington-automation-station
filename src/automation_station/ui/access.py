"""Simple role-based access for Automation Station.

Same architecture as pax_americana.ui.access:
  - ADMIN: Full access including settings, API keys, hardware config.
  - VIEWER: Read-only access to results and analysis pages.

Usage in pages that require admin:
    from automation_station.ui.access import require_admin
    if not require_admin():
        st.stop()
"""
import hashlib
import json
from pathlib import Path

import streamlit as st

_ACCESS_FILE = Path("data/manual/access.json")

# Default password: "REDACTED_DEFAULT_PASSWORD" — change on first run
_DEFAULT_HASH = hashlib.sha256("REDACTED_DEFAULT_PASSWORD".encode()).hexdigest()


def _load_access() -> dict:
    if _ACCESS_FILE.exists():
        return json.loads(_ACCESS_FILE.read_text())
    return {"admin_hash": _DEFAULT_HASH}


def _save_access(data: dict):
    _ACCESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _ACCESS_FILE.write_text(json.dumps(data, indent=2))


def _hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


def is_admin() -> bool:
    """Check if current session is authenticated as admin."""
    return st.session_state.get("hw_admin", False)


def require_admin() -> bool:
    """Gate a page behind admin authentication. Returns True if admin."""
    if is_admin():
        return True

    st.warning("This page requires admin access.")
    pw = st.text_input("Admin password", type="password", key="hw_admin_pw_input")
    if pw and st.button("Login", type="primary"):
        access = _load_access()
        if _hash_password(pw) == access.get("admin_hash", _DEFAULT_HASH):
            st.session_state["hw_admin"] = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    return False


def set_admin_password(old_pw: str, new_pw: str) -> bool:
    """Change the admin password. Returns True on success."""
    access = _load_access()
    if _hash_password(old_pw) != access.get("admin_hash", _DEFAULT_HASH):
        return False
    access["admin_hash"] = _hash_password(new_pw)
    _save_access(access)
    return True


def admin_logout():
    """Clear admin session."""
    st.session_state["hw_admin"] = False
