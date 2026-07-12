"""Read-only environment status for the Settings screen: GPU and providers."""

from __future__ import annotations

import json
import shutil
import subprocess
import urllib.request
from typing import Any

from . import settings


def gpu_status() -> dict[str, Any]:
    smi = shutil.which("nvidia-smi")
    if not smi:
        return {"available": False, "device": "CPU only"}
    try:
        out = subprocess.run(
            [smi, "--query-gpu=name,memory.total,memory.used,driver_version",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10,
        )
        if out.returncode != 0 or not out.stdout.strip():
            return {"available": False, "device": "CPU only"}
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
        return {"available": False, "device": "unknown"}


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
