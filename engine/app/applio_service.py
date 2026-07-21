"""Applio (RVC) integration: voice conversion as a subprocess call.

Applio ships a complete CLI in core.py; conversion is one invocation in
its own virtual environment. No server to keep alive.
"""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from typing import Any

from . import settings


class ApplioError(RuntimeError):
    pass


async def convert(params: dict[str, Any]) -> dict[str, Any]:
    """Run RVC inference: re-voice input_path with the model at pth_path.

    Required params: input_path, output_path, pth_path, index_path.
    Optional: pitch (semitones), f0_method, index_rate, protect, and the
    voice-shaping set: autotune, autotune_strength, clean_audio, clean_strength.

    Applio checks the two strength values against a 0.1 grid and rejects
    anything off it, so callers must keep to one decimal place.
    """
    python = settings.applio_python()
    if not python.exists():
        raise ApplioError(
            f"The voice model (Applio) isn't installed yet. {settings.setup_hint()}"
        )

    input_path = Path(params["input_path"])
    if not input_path.exists():
        raise ApplioError(f"Input audio not found: {input_path}")
    output_path = Path(params["output_path"])
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        str(python),
        "core.py",
        "infer",
        "--input_path", str(input_path),
        "--output_path", str(output_path),
        "--pth_path", str(params["pth_path"]),
        "--index_path", str(params["index_path"]),
        "--pitch", str(params.get("pitch", 0)),
        "--f0_method", str(params.get("f0_method", "rmvpe")),
        "--index_rate", str(params.get("index_rate", 0.3)),
        "--protect", str(params.get("protect", 0.33)),
        "--f0_autotune", "True" if params.get("autotune") else "False",
        "--f0_autotune_strength", str(round(float(params.get("autotune_strength", 1.0)), 1)),
        "--clean_audio", "True" if params.get("clean_audio") else "False",
        "--clean_strength", str(round(float(params.get("clean_strength", 0.7)), 1)),
        "--export_format", "WAV",
    ]

    def _run() -> subprocess.CompletedProcess:
        return subprocess.run(
            cmd,
            cwd=str(settings.APPLIO_DIR),
            capture_output=True,
            text=True,
            timeout=1800,
        )

    proc = await asyncio.to_thread(_run)
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip()[-2000:]
        raise ApplioError(f"Applio inference failed (exit {proc.returncode}): {tail}")
    if not output_path.exists():
        raise ApplioError(f"Applio reported success but {output_path} does not exist")
    return {"audio_path": str(output_path)}
