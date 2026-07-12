"""Engine configuration from environment variables, with sane defaults."""

from __future__ import annotations

import os
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parent.parent

# Mock mode: exercise the full job pipeline without GPU models.
MOCK = os.getenv("CADENCE_MOCK", "0") == "1"

# Where generated and converted audio lands.
OUTPUT_DIR = Path(os.getenv("CADENCE_OUTPUT_DIR", ENGINE_ROOT / "output"))

# Local database and raw voice recordings.
DB_PATH = Path(os.getenv("CADENCE_DB_PATH", ENGINE_ROOT / "cadence.db"))
VOICE_DATA_DIR = Path(os.getenv("CADENCE_VOICE_DATA_DIR", ENGINE_ROOT / "voice_data"))

# Clean speech required before voice training unlocks (seconds).
VOICE_UNLOCK_SECONDS = int(os.getenv("CADENCE_VOICE_UNLOCK_SECONDS", "600"))
# Default RVC training length; a real voice wants more, tests override this.
VOICE_TRAIN_EPOCHS = int(os.getenv("CADENCE_VOICE_TRAIN_EPOCHS", "100"))

# ACE-Step vendor install and its API server.
ACESTEP_DIR = Path(os.getenv("CADENCE_ACESTEP_DIR", ENGINE_ROOT / "vendor" / "ACE-Step-1.5"))
ACESTEP_PORT = int(os.getenv("CADENCE_ACESTEP_PORT", "8001"))
ACESTEP_URL = f"http://127.0.0.1:{ACESTEP_PORT}"
# First launch downloads ~10 GB of model weights; allow a long readiness window.
ACESTEP_READY_TIMEOUT = int(os.getenv("CADENCE_ACESTEP_READY_TIMEOUT", "1800"))

# Applio vendor install (voice conversion).
APPLIO_DIR = Path(os.getenv("CADENCE_APPLIO_DIR", ENGINE_ROOT / "vendor" / "Applio"))

# Local text provider (lyrics/style structuring). Ollama over IPv4.
OLLAMA_URL = os.getenv("CADENCE_OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("CADENCE_OLLAMA_MODEL", "qwen3.5:9b")

# Cloud text provider (optional). Claude, keyed from the OS keychain.
CLAUDE_MODEL = os.getenv("CADENCE_CLAUDE_MODEL", "claude-opus-4-8")


def acestep_python() -> Path:
    return ACESTEP_DIR / ".venv" / "Scripts" / "python.exe"


def applio_python() -> Path:
    return APPLIO_DIR / ".venv" / "Scripts" / "python.exe"
