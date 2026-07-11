"""Cadence engine: local FastAPI service the desktop shell talks to.

Phase 1 surface:
    GET  /ping                liveness
    GET  /health              engine + backend readiness detail
    POST /generate            queue a music generation job
    POST /convert-voice       queue an RVC voice conversion job
    GET  /status/{job_id}     job state
    GET  /jobs                all jobs, newest first
    GET  /audio/{job_id}      download a finished job's audio
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import acestep_service, applio_service, mock_audio, settings
from .jobs import Job, JobStatus, queue

app = FastAPI(title="Cadence Engine")


@app.get("/ping")
def ping() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "mock": settings.MOCK,
        "acestep_installed": settings.acestep_python().exists(),
        "acestep_running": False if settings.MOCK else acestep_service.is_healthy(),
        "applio_installed": settings.applio_python().exists(),
    }


class GenerateRequest(BaseModel):
    prompt: str = ""
    lyrics: str = ""
    sample_query: str = ""
    instrumental: bool = False
    vocal_language: Optional[str] = None
    bpm: Optional[int] = Field(default=None, ge=30, le=300)
    duration: Optional[float] = Field(default=None, ge=10, le=600)
    key_scale: str = ""
    time_signature: str = ""
    inference_steps: int = Field(default=8, ge=1, le=200)
    thinking: bool = True


class ConvertVoiceRequest(BaseModel):
    input_path: str
    pth_path: str = ""
    index_path: str = ""
    pitch: int = Field(default=0, ge=-24, le=24)
    f0_method: str = "rmvpe"
    index_rate: float = Field(default=0.3, ge=0.0, le=1.0)
    protect: float = Field(default=0.33, ge=0.0, le=0.5)


async def _run_music_job(job: Job) -> None:
    job.update(status=JobStatus.GENERATING, detail="Generating music")
    if settings.MOCK:
        out = settings.OUTPUT_DIR / f"mock-{job.id}.wav"
        mock_audio.write_mock_track(out, seconds=10.0)
        job.result = {"audio_path": str(out), "metas": {"mock": True}, "seed": "0"}
    else:
        job.result = await acestep_service.generate(
            job.params, progress=lambda msg: job.update(detail=msg)
        )
    job.update(status=JobStatus.DONE, detail="Done")


async def _run_voice_job(job: Job) -> None:
    job.update(status=JobStatus.CONVERTING, detail="Converting to your voice")
    if settings.MOCK:
        src = Path(job.params["input_path"])
        if not src.exists():
            raise applio_service.ApplioError(f"Input audio not found: {src}")
        out = settings.OUTPUT_DIR / f"mock-voice-{job.id}.wav"
        mock_audio.write_mock_conversion(src, out)
        job.result = {"audio_path": str(out)}
    else:
        job.params.setdefault(
            "output_path", str(settings.OUTPUT_DIR / f"voice-{job.id}.wav")
        )
        job.result = await applio_service.convert(job.params)
    job.update(status=JobStatus.DONE, detail="Done")


@app.post("/generate")
async def generate(req: GenerateRequest) -> dict:
    if not (req.prompt or req.lyrics or req.sample_query):
        raise HTTPException(422, "Provide a prompt, lyrics, or sample_query")
    params = req.model_dump()
    params["audio_duration"] = params.pop("duration")
    job = queue.submit(Job(kind="music", params=params), _run_music_job)
    return {"job_id": job.id}


@app.post("/convert-voice")
async def convert_voice(req: ConvertVoiceRequest) -> dict:
    if not settings.MOCK and (not req.pth_path or not req.index_path):
        raise HTTPException(422, "pth_path and index_path are required outside mock mode")
    job = queue.submit(Job(kind="voice", params=req.model_dump()), _run_voice_job)
    return {"job_id": job.id}


@app.get("/status/{job_id}")
def status(job_id: str) -> dict:
    job = queue.get(job_id)
    if job is None:
        raise HTTPException(404, "No such job")
    return job.to_dict()


@app.get("/jobs")
def jobs() -> list[dict]:
    return [j.to_dict() for j in queue.all()]


@app.get("/audio/{job_id}")
def audio(job_id: str) -> FileResponse:
    job = queue.get(job_id)
    if job is None:
        raise HTTPException(404, "No such job")
    if job.status is not JobStatus.DONE or not job.result:
        raise HTTPException(409, f"Job is {job.status.value}, not done")
    path = Path(job.result["audio_path"])
    if not path.exists():
        raise HTTPException(410, "Result file no longer exists")
    return FileResponse(path, media_type="audio/wav", filename=path.name)


@app.on_event("shutdown")
def _shutdown() -> None:
    acestep_service.shutdown()
