"""API keys, stored in the OS keychain via keyring — never in plaintext.

On Windows this is the Credential Manager. The engine owns the keys
because it is what calls the provider APIs; only their set/unset status
is ever exposed, never the values.
"""

from __future__ import annotations

import keyring

SERVICE = "cadence"
KNOWN = ("claude", "openai", "gemini", "suno", "elevenlabs")


def set_secret(name: str, value: str) -> None:
    if name not in KNOWN:
        raise ValueError(f"Unknown secret: {name}")
    keyring.set_password(SERVICE, name, value)


def get_secret(name: str) -> str | None:
    if name not in KNOWN:
        return None
    return keyring.get_password(SERVICE, name)


def clear_secret(name: str) -> None:
    if name not in KNOWN:
        return
    try:
        keyring.delete_password(SERVICE, name)
    except keyring.errors.PasswordDeleteError:
        pass


def status() -> dict[str, bool]:
    """Which keys are set — booleans only, never the values."""
    return {name: bool(get_secret(name)) for name in KNOWN}
