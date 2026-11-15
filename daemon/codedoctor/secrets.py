"""API keys: read from the endpoint's environment variable, or from the OS credential store.

Keys never go into the project configuration, the journal or any log. The desktop
app writes them to Windows Credential Manager (service 'codedoctor', account =
endpoint id) through `set_key`; the daemon only ever reads them.
"""

from __future__ import annotations

import os

SERVICE = "codedoctor"


def _keyring():
    try:
        import keyring

        return keyring
    except Exception:  # keyring missing or no backend: env vars still work
        return None


def get_key(endpoint) -> str | None:
    if endpoint.api_key_env:
        value = os.environ.get(endpoint.api_key_env)
        if value:
            return value
    if getattr(endpoint, "api_key_keyring", False):
        kr = _keyring()
        if kr is not None:
            try:
                return kr.get_password(SERVICE, endpoint.id) or None
            except Exception:
                return None
    return None


def set_key(endpoint_id: str, key: str) -> None:
    kr = _keyring()
    if kr is None:
        raise RuntimeError("the system credential store is not available; use an environment variable instead")
    kr.set_password(SERVICE, endpoint_id, key)


def delete_key(endpoint_id: str) -> None:
    """Remove the saved key. Nothing saved is nothing to do; a failure to remove it is raised, so the settings window
    says so instead of "saved" (Haiku check item 11: the error used to be swallowed)."""
    kr = _keyring()
    if kr is None:
        return  # no credential store: no key could have been saved in it
    if kr.get_password(SERVICE, endpoint_id) is None:
        return
    kr.delete_password(SERVICE, endpoint_id)


def key_status(endpoint) -> str:
    """'not_needed' | 'env' | 'keyring' | 'missing'"""
    if not endpoint.api_key_env and not getattr(endpoint, "api_key_keyring", False):
        return "not_needed"
    if endpoint.api_key_env and os.environ.get(endpoint.api_key_env):
        return "env"
    if getattr(endpoint, "api_key_keyring", False):
        kr = _keyring()
        try:
            if kr is not None and kr.get_password(SERVICE, endpoint.id):
                return "keyring"
        except Exception:
            pass
    return "missing"
