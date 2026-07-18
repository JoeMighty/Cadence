"""API keys, stored in the OS keychain via keyring — never in plaintext.

Windows uses the Credential Manager, macOS the Keychain, Linux the Secret
Service (GNOME Keyring / KWallet). If no keyring backend is available — a
headless Linux box, say — storage degrades gracefully: reads return None and
status reports everything unset, so the local Ollama provider still works
without any key.
"""

from __future__ import annotations

import keyring
import keyring.errors

SERVICE = "cadence"
KNOWN = ("claude", "openai", "gemini", "suno", "elevenlabs")


class KeyringUnavailable(RuntimeError):
    """No OS keychain is available to store a secret."""


def set_secret(name: str, value: str) -> None:
    if name not in KNOWN:
        raise ValueError(f"Unknown secret: {name}")
    try:
        keyring.set_password(SERVICE, name, value)
    except keyring.errors.KeyringError as exc:
        raise KeyringUnavailable(
            "No OS keychain is available to store the key. On Linux, install and "
            "start a Secret Service backend (GNOME Keyring or KWallet), or use the "
            "local Ollama provider, which needs no key."
        ) from exc


def get_secret(name: str) -> str | None:
    if name not in KNOWN:
        return None
    try:
        return keyring.get_password(SERVICE, name)
    except keyring.errors.KeyringError:
        return None


def clear_secret(name: str) -> None:
    if name not in KNOWN:
        return
    try:
        keyring.delete_password(SERVICE, name)
    except keyring.errors.KeyringError:
        pass


def status() -> dict[str, bool]:
    """Which keys are set — booleans only, never the values."""
    return {name: bool(get_secret(name)) for name in KNOWN}
