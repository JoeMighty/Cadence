"""Vocal stem separation so RVC re-voices only the vocal, not the full mix.

Demucs runs in the Applio virtual environment (which already has torch and
CUDA). When separation is unavailable the caller falls back to converting
the full mix, preserving the prior behavior.
"""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from typing import Optional

from . import settings


class StemError(RuntimeError):
    pass


_available: Optional[bool] = None


def available() -> bool:
    """True if Demucs can run in the Applio venv. Cached after first check."""
    global _available
    if _available is not None:
        return _available
    python = settings.applio_python()
    if not python.exists():
        _available = False
        return _available
    try:
        proc = subprocess.run(
            [str(python), "-c", "import demucs"], capture_output=True, timeout=30
        )
        _available = proc.returncode == 0
    except Exception:
        _available = False
    return _available


async def _run(cmd: list[str]) -> None:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(settings.APPLIO_DIR),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    out, _ = await proc.communicate()
    if proc.returncode != 0:
        tail = out.decode(errors="replace")[-1000:]
        raise StemError(f"{Path(cmd[1]).name if cmd[1:2] else 'step'} failed (exit {proc.returncode}):\n{tail}")


async def separate(mix_path: Path, work_dir: Path) -> tuple[Path, Path]:
    """Split a mix into (vocals, instrumental) with Demucs two-stems."""
    python = settings.applio_python()
    work_dir.mkdir(parents=True, exist_ok=True)
    await _run([
        str(python), "-m", "demucs",
        "--two-stems", "vocals",
        "-n", "htdemucs",
        "--device", "cuda",
        "-o", str(work_dir),
        str(mix_path),
    ])
    base = work_dir / "htdemucs" / mix_path.stem
    vocal, instrumental = base / "vocals.wav", base / "no_vocals.wav"
    if not vocal.exists() or not instrumental.exists():
        raise StemError(f"Demucs produced no stems in {base}")
    return vocal, instrumental


async def remix(vocal: Path, instrumental: Path, out_path: Path) -> None:
    """Sum a converted vocal back over its instrumental."""
    python = settings.applio_python()
    helper = Path(__file__).parent / "remix_helper.py"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    await _run([str(python), str(helper), str(vocal), str(instrumental), str(out_path)])
    if not out_path.exists():
        raise StemError(f"Remix produced no file at {out_path}")
