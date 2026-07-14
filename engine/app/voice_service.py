"""Voice profile takes and RVC training.

Takes are raw WAV recordings saved under voice_data/<profile_id>/takes.
Training runs Applio's pipeline (preprocess -> extract -> train) as a
background job, parses epoch progress from stdout, then records the
resulting inference model and index on the profile.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import re
import shutil
import wave
from pathlib import Path
from typing import Any, Callable, Optional

from . import db, settings
from .jobs import Job, JobStatus


class VoiceError(RuntimeError):
    pass


SAMPLE_RATE = 40000  # matches the 40k pretrained generator/discriminator
_EPOCH_RE = re.compile(r"epoch=(\d+)")


def _takes_dir(profile_id: str) -> Path:
    return settings.VOICE_DATA_DIR / profile_id / "takes"


def wav_seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as wf:
        return wf.getnframes() / float(wf.getframerate())


def save_take(profile_id: str, wav_bytes: bytes, script_index: Optional[int]) -> dict[str, Any]:
    profile = db.get_profile(profile_id)
    if profile is None:
        raise VoiceError("No such voice profile")
    takes = _takes_dir(profile_id)
    takes.mkdir(parents=True, exist_ok=True)
    tid_path = takes / f"{os.urandom(6).hex()}.wav"
    tid_path.write_bytes(wav_bytes)
    try:
        seconds = wav_seconds(tid_path)
    except wave.Error as exc:
        tid_path.unlink(missing_ok=True)
        raise VoiceError(f"Uploaded file is not a valid WAV: {exc}") from exc
    take = db.add_take(profile_id, tid_path.name, seconds, script_index)
    return take


def remove_take(take_id: str) -> None:
    take = db.get_take(take_id)
    if take is None:
        return
    path = _takes_dir(take["profile_id"]) / take["filename"]
    path.unlink(missing_ok=True)
    db.delete_take(take_id)


async def _run_step(cmd: list[str], on_line: Callable[[str], None] | None = None) -> None:
    """Run an Applio CLI step in its venv, streaming stdout line by line."""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(settings.APPLIO_DIR),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    assert proc.stdout is not None
    tail: list[str] = []
    async for raw in proc.stdout:
        line = raw.decode(errors="replace").rstrip()
        tail.append(line)
        if len(tail) > 40:
            tail.pop(0)
        if on_line is not None:
            on_line(line)
    await proc.wait()
    if proc.returncode != 0:
        raise VoiceError(f"Step failed (exit {proc.returncode}): {' '.join(cmd[2:4])}\n" + "\n".join(tail[-8:]))


def _find_model(profile_id: str) -> tuple[Path, Path]:
    log_dir = settings.APPLIO_DIR / "logs" / profile_id
    models = sorted(
        log_dir.glob(f"{profile_id}_*e_*s.pth"),
        key=lambda p: p.stat().st_mtime,
    )
    index = log_dir / f"{profile_id}.index"
    if not models:
        raise VoiceError(f"Training produced no inference model in {log_dir}")
    if not index.exists():
        raise VoiceError(f"Training produced no index file in {log_dir}")
    return models[-1], index


async def train(job: Job, profile_id: str, epochs: int) -> None:
    profile = db.get_profile(profile_id)
    if profile is None:
        raise VoiceError("No such voice profile")

    db.update_profile(profile_id, status="training", detail="Preparing recordings", error=None)
    job.update(status=JobStatus.GENERATING, detail="Preparing recordings")

    if settings.MOCK:
        for e in range(1, epochs + 1):
            await asyncio.sleep(0.05)
            db.update_profile(profile_id, detail=f"Training epoch {e}/{epochs}")
            job.update(detail=f"Training epoch {e}/{epochs}")
        model_path = str(settings.VOICE_DATA_DIR / profile_id / "mock_model.pth")
        Path(model_path).parent.mkdir(parents=True, exist_ok=True)
        Path(model_path).write_bytes(b"mock")
        db.update_profile(
            profile_id, status="ready", detail="Ready",
            model_path=model_path, index_path=model_path,
            epochs=epochs, trained_at=asyncio.get_running_loop().time(),
        )
        job.result = {"profile_id": profile_id, "model_path": model_path}
        job.update(status=JobStatus.DONE, detail="Done")
        return

    python = settings.applio_python()
    if not python.exists():
        raise VoiceError(f"The voice model (Applio) isn't installed yet. {settings.setup_hint()}")
    dataset = _takes_dir(profile_id)
    if not any(dataset.glob("*.wav")):
        raise VoiceError("No recordings to train on")

    cores = str(min(8, os.cpu_count() or 4))

    def progress(line: str) -> None:
        m = _EPOCH_RE.search(line)
        if m:
            msg = f"Training epoch {m.group(1)}/{epochs}"
            db.update_profile(profile_id, detail=msg)
            job.update(detail=msg)

    # 1. preprocess the raw takes into training segments
    db.update_profile(profile_id, detail="Preparing recordings")
    job.update(detail="Preparing recordings")
    await _run_step([
        str(python), "core.py", "preprocess",
        "--model_name", profile_id,
        "--dataset_path", str(dataset),
        "--sample_rate", str(SAMPLE_RATE),
        "--cut_preprocess", "Automatic",
    ])

    # 2. extract features (cpu_cores must be set explicitly, see Applio bug)
    db.update_profile(profile_id, detail="Analyzing voice")
    job.update(detail="Analyzing voice")
    await _run_step([
        str(python), "core.py", "extract",
        "--model_name", profile_id,
        "--sample_rate", str(SAMPLE_RATE),
        "--include_mutes", "2",
        "--gpu", "0",
        "--cpu_cores", cores,
    ])

    # 3. train; the final epoch extracts the inference model
    await _run_step([
        str(python), "core.py", "train",
        "--model_name", profile_id,
        "--sample_rate", str(SAMPLE_RATE),
        "--save_every_epoch", "10",
        "--total_epoch", str(epochs),
        "--batch_size", "4",
        "--gpu", "0",
    ], on_line=progress)

    model_path, index_path = _find_model(profile_id)
    db.update_profile(
        profile_id, status="ready", detail="Ready",
        model_path=str(model_path), index_path=str(index_path),
        epochs=epochs, trained_at=_now(),
    )
    job.result = {"profile_id": profile_id, "model_path": str(model_path)}
    job.update(status=JobStatus.DONE, detail="Done")


def _now() -> float:
    import time
    return time.time()


def mark_failed(profile_id: str, message: str) -> None:
    with contextlib.suppress(Exception):
        db.update_profile(profile_id, status="error", detail="Failed", error=message)
