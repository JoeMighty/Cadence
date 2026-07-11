"""Engine configuration from environment variables, with sane defaults."""

from __future__ import annotations

import os
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parent.parent

# Mock mode: exercise the full job pipeline without GPU models.
MOCK = os.getenv("CADENCE_MOCK", "0") == "1"

# Where generated and converted audio lands.
OUTPUT_DIR = Path(os.getenv("CADENCE_OUTPUT_DIR", ENGINE_ROOT / "output"))

# ACE-Step vendor install and its API server.
ACESTEP_DIR = Path(os.getenv("CADENCE_ACESTEP_DIR", ENGINE_ROOT / "vendor" / "ACE-Step-1.5"))
ACESTEP_PORT = int(os.getenv("CADENCE_ACESTEP_PORT", "8001"))
ACESTEP_URL = f"http://127.0.0.1:{ACESTEP_PORT}"
# First launch downloads ~10 GB of model weights; allow a long readiness window.
ACESTEP_READY_TIMEOUT = int(os.getenv("CADENCE_ACESTEP_READY_TIMEOUT", "1800"))

# Applio vendor install (voice conversion).
APPLIO_DIR = Path(os.getenv("CADENCE_APPLIO_DIR", ENGINE_ROOT / "vendor" / "Applio"))


def acestep_python() -> Path:
    return ACESTEP_DIR / ".venv" / "Scripts" / "python.exe"


def applio_python() -> Path:
    return APPLIO_DIR / ".venv" / "Scripts" / "python.exe"
