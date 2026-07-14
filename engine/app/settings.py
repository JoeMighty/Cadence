"""Engine configuration from environment variables, with sane defaults."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parent.parent

# When bundled by PyInstaller, ENGINE_ROOT points into a temp extraction dir,
# so writable data (db, audio, recordings) goes to a per-user location instead.
FROZEN = getattr(sys, "frozen", False)
if FROZEN:
    DATA_ROOT = Path(
        os.getenv("CADENCE_DATA_DIR")
        or Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / "Cadence"
    )
    # The heavy AI backends can't ship in the installer; they live in a stable
    # per-user folder that scripts/setup-backends installs into.
    VENDOR_ROOT = DATA_ROOT / "vendor"
else:
    DATA_ROOT = ENGINE_ROOT
    VENDOR_ROOT = ENGINE_ROOT / "vendor"

# Mock mode: exercise the full job pipeline without GPU models.
MOCK = os.getenv("CADENCE_MOCK", "0") == "1"

# Where generated and converted audio lands.
OUTPUT_DIR = Path(os.getenv("CADENCE_OUTPUT_DIR", DATA_ROOT / "output"))

# Local database and raw voice recordings.
DB_PATH = Path(os.getenv("CADENCE_DB_PATH", DATA_ROOT / "cadence.db"))
VOICE_DATA_DIR = Path(os.getenv("CADENCE_VOICE_DATA_DIR", DATA_ROOT / "voice_data"))

# Clean speech required before voice training unlocks (seconds).
VOICE_UNLOCK_SECONDS = int(os.getenv("CADENCE_VOICE_UNLOCK_SECONDS", "600"))
# Default RVC training length; a real voice wants more, tests override this.
VOICE_TRAIN_EPOCHS = int(os.getenv("CADENCE_VOICE_TRAIN_EPOCHS", "100"))

# ACE-Step vendor install and its API server.
ACESTEP_DIR = Path(os.getenv("CADENCE_ACESTEP_DIR", VENDOR_ROOT / "ACE-Step-1.5"))
ACESTEP_PORT = int(os.getenv("CADENCE_ACESTEP_PORT", "8001"))
ACESTEP_URL = f"http://127.0.0.1:{ACESTEP_PORT}"
# First launch downloads ~10 GB of model weights; allow a long readiness window.
ACESTEP_READY_TIMEOUT = int(os.getenv("CADENCE_ACESTEP_READY_TIMEOUT", "1800"))

# Applio vendor install (voice conversion).
APPLIO_DIR = Path(os.getenv("CADENCE_APPLIO_DIR", VENDOR_ROOT / "Applio"))

# Local text provider (lyrics/style structuring). Ollama over IPv4.
OLLAMA_URL = os.getenv("CADENCE_OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("CADENCE_OLLAMA_MODEL", "qwen3.5:9b")

# Cloud text provider (optional). Claude, keyed from the OS keychain.
CLAUDE_MODEL = os.getenv("CADENCE_CLAUDE_MODEL", "claude-opus-4-8")


def setup_hint() -> str:
    """How to install the missing AI backends, worded for how Cadence is running."""
    if FROZEN:
        return (
            f"Install the AI backends into {VENDOR_ROOT} by running the one-time "
            "setup script (scripts/setup-backends.ps1). See "
            "https://joemighty.github.io/Cadence/setup.html."
        )
    return "Run scripts/setup-backends.ps1, or 'uv sync' inside each engine/vendor backend."


def acestep_python() -> Path:
    return ACESTEP_DIR / ".venv" / "Scripts" / "python.exe"


def applio_python() -> Path:
    return APPLIO_DIR / ".venv" / "Scripts" / "python.exe"
