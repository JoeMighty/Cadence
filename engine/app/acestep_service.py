"""ACE-Step integration: child API server lifecycle plus a thin REST client.

ACE-Step runs in its own virtual environment as a separate process (its
dependency set must never mix with Applio's). The engine starts it on
demand, waits for /health, and then drives it over localhost REST:

    POST /release_task  -> {task_id}
    POST /query_result  -> status 0 queued/running, 1 done, 2 failed
    GET  /v1/audio?path= -> audio bytes
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Optional

from . import settings


class AceStepError(RuntimeError):
    pass


_process: Optional[subprocess.Popen] = None


def _http(method: str, url: str, payload: dict | None = None, timeout: float = 30.0) -> Any:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def is_healthy() -> bool:
    try:
        _http("GET", f"{settings.ACESTEP_URL}/health", timeout=3)
        return True
    except Exception:
        return False


def _spawn() -> None:
    global _process
    if _process is not None and _process.poll() is None:
        return
    python = settings.acestep_python()
    if not python.exists():
        raise AceStepError(
            f"The music model (ACE-Step) isn't installed yet. {settings.setup_hint()}"
        )
    _process = subprocess.Popen(
        [str(python), "-m", "acestep.api_server", "--port", str(settings.ACESTEP_PORT)],
        cwd=str(settings.ACESTEP_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
    )


async def ensure_running(progress=None) -> None:
    """Start the ACE-Step server if needed and wait until it reports healthy.

    First-ever launch also downloads model weights (~10 GB), so the wait
    is generous and reports what is happening through `progress`.
    """
    if is_healthy():
        return
    _spawn()
    waited = 0
    step = 5
    while waited < settings.ACESTEP_READY_TIMEOUT:
        await asyncio.sleep(step)
        waited += step
        if is_healthy():
            return
        if _process is not None and _process.poll() is not None:
            raise AceStepError(
                f"ACE-Step server exited with code {_process.returncode} during startup."
            )
        if progress is not None:
            progress(f"Starting music model server ({waited}s)")
    raise AceStepError("Timed out waiting for the ACE-Step server to become ready.")


async def generate(
    params: dict[str, Any], progress=None, out_path: Path | None = None
) -> dict[str, Any]:
    """Submit a text2music task, poll to completion, download the audio.

    Lands on out_path when given, else OUTPUT_DIR/<task id>.wav.
    Returns {"audio_path": ..., "metas": {...}, "seed": ...}.
    """
    await ensure_running(progress)

    body = {
        "prompt": params.get("prompt", ""),
        "lyrics": params.get("lyrics", ""),
        "thinking": params.get("thinking", True),
        "audio_format": params.get("audio_format", "wav"),
        "batch_size": 1,
        "inference_steps": params.get("inference_steps", 8),
    }
    for key in ("vocal_language", "bpm", "audio_duration", "key_scale", "time_signature", "sample_query"):
        value = params.get(key)
        if value not in (None, ""):
            body[key] = value
    if params.get("instrumental"):
        body["instrumental"] = True
    # Repaint: regenerate a time range of an existing track, keeping the rest.
    if params.get("task_type"):
        body["task_type"] = params["task_type"]
        for key in ("src_audio_path", "repainting_start", "repainting_end", "repaint_mode"):
            value = params.get(key)
            if value is not None:
                body[key] = value

    data = await asyncio.to_thread(_http, "POST", f"{settings.ACESTEP_URL}/release_task", body, 120.0)
    task_id = (data.get("data") or {}).get("task_id")
    if not task_id:
        raise AceStepError(f"release_task returned no task_id: {data}")

    while True:
        await asyncio.sleep(3)
        res = await asyncio.to_thread(
            _http, "POST", f"{settings.ACESTEP_URL}/query_result", {"task_id_list": [task_id]}, 30.0
        )
        entries = res.get("data") or []
        if not entries:
            continue
        status = entries[0].get("status")
        if status == 0:
            if progress is not None:
                progress("Generating music")
            continue
        if status == 2:
            raise AceStepError(f"ACE-Step reported failure for task {task_id}")
        results = json.loads(entries[0]["result"])
        if not results:
            raise AceStepError("ACE-Step returned an empty result list")
        first = results[0]
        audio_url = first["file"]
        metas = first.get("metas") or {}
        seed = first.get("seed_value", "")
        break

    out = out_path or settings.OUTPUT_DIR / f"{task_id}.wav"
    out.parent.mkdir(parents=True, exist_ok=True)
    full_url = settings.ACESTEP_URL + audio_url if audio_url.startswith("/") else audio_url

    def _download() -> None:
        with urllib.request.urlopen(full_url, timeout=120) as resp, open(out, "wb") as fh:
            fh.write(resp.read())

    await asyncio.to_thread(_download)
    return {"audio_path": str(out), "metas": metas, "seed": seed}


def shutdown() -> None:
    global _process
    if _process is not None and _process.poll() is None:
        _process.terminate()
    _process = None
