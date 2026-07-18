"""Read-only environment status for the Settings screen: GPU and providers."""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
import sys
import urllib.request
from typing import Any

from . import settings


def _nvidia_status() -> dict[str, Any] | None:
    """Rich NVIDIA detail via nvidia-smi (Windows and Linux). None if unavailable."""
    smi = shutil.which("nvidia-smi")
    if not smi:
        return None
    try:
        out = subprocess.run(
            [smi, "--query-gpu=name,memory.total,memory.used,driver_version",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10,
        )
        if out.returncode != 0 or not out.stdout.strip():
            return None
        name, total, used, driver = [x.strip() for x in out.stdout.strip().split(",")]
        return {
            "available": True,
            "device": name,
            "cuda": True,
            "vram_total_mb": int(float(total)),
            "vram_used_mb": int(float(used)),
            "driver": driver,
        }
    except Exception:
        return None


def gpu_status() -> dict[str, Any]:
    nvidia = _nvidia_status()
    if nvidia is not None:
        return nvidia
    # Apple Silicon: every M-series chip has a Metal GPU that torch drives via MPS.
    if sys.platform == "darwin" and platform.machine() == "arm64":
        return {"available": True, "device": "Apple Silicon GPU (MPS)", "mps": True}
    return {"available": False, "device": "CPU only"}


def ollama_status() -> dict[str, Any]:
    try:
        req = urllib.request.Request(f"{settings.OLLAMA_URL}/api/tags")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
        models = [m.get("name", "") for m in data.get("models", [])]
        return {
            "reachable": True,
            "model": settings.OLLAMA_MODEL,
            "model_present": settings.OLLAMA_MODEL in models,
        }
    except Exception:
        return {"reachable": False, "model": settings.OLLAMA_MODEL, "model_present": False}
