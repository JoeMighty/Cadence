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

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import acestep_service, applio_service, db, mock_audio, settings, voice_service
from .jobs import Job, JobStatus, queue

app = FastAPI(title="Cadence Engine")

# The engine is local-only; the desktop webview talks to it cross-origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    db.init_db()


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


# ------------------------- voice training -------------------------

class CreateProfileRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    sample_rate: int = 40000


class TrainRequest(BaseModel):
    epochs: int = Field(default=settings.VOICE_TRAIN_EPOCHS, ge=1, le=1000)


def _with_unlock(profile: dict) -> dict:
    profile["unlock_seconds"] = settings.VOICE_UNLOCK_SECONDS
    profile["can_train"] = (
        profile.get("total_seconds", 0) >= settings.VOICE_UNLOCK_SECONDS
        and profile.get("status") in ("collecting", "ready", "error")
    )
    return profile


@app.post("/voice/profiles")
def create_voice_profile(req: CreateProfileRequest) -> dict:
    return _with_unlock(db.create_profile(req.name, req.sample_rate))


@app.get("/voice/profiles")
def list_voice_profiles() -> list[dict]:
    return [_with_unlock(p) for p in db.list_profiles()]


@app.get("/voice/profiles/{profile_id}")
def get_voice_profile(profile_id: str) -> dict:
    profile = db.get_profile(profile_id)
    if profile is None:
        raise HTTPException(404, "No such voice profile")
    return _with_unlock(profile)


@app.delete("/voice/profiles/{profile_id}")
def delete_voice_profile(profile_id: str) -> dict:
    db.delete_profile(profile_id)
    return {"deleted": profile_id}


@app.post("/voice/profiles/{profile_id}/takes")
async def upload_take(profile_id: str, request: Request, script_index: int | None = None) -> dict:
    body = await request.body()
    if not body:
        raise HTTPException(422, "Empty request body; send WAV bytes")
    try:
        take = voice_service.save_take(profile_id, body, script_index)
    except voice_service.VoiceError as exc:
        raise HTTPException(422, str(exc))
    return {"take": take, "profile": _with_unlock(db.get_profile(profile_id))}


@app.get("/voice/profiles/{profile_id}/takes")
def get_takes(profile_id: str) -> list[dict]:
    if db.get_profile(profile_id) is None:
        raise HTTPException(404, "No such voice profile")
    return db.list_takes(profile_id)


@app.delete("/voice/takes/{take_id}")
def delete_take(take_id: str) -> dict:
    voice_service.remove_take(take_id)
    return {"deleted": take_id}


@app.post("/voice/profiles/{profile_id}/train")
async def train_voice(profile_id: str, req: TrainRequest) -> dict:
    profile = db.get_profile(profile_id)
    if profile is None:
        raise HTTPException(404, "No such voice profile")
    if profile["status"] == "training":
        raise HTTPException(409, "This voice is already training")
    if not settings.MOCK and profile["total_seconds"] < settings.VOICE_UNLOCK_SECONDS:
        raise HTTPException(
            409,
            f"Need {settings.VOICE_UNLOCK_SECONDS}s of audio, have "
            f"{int(profile['total_seconds'])}s",
        )

    async def runner(job: Job) -> None:
        try:
            await voice_service.train(job, profile_id, req.epochs)
        except Exception as exc:  # noqa: BLE001 - surface failure on the profile too
            voice_service.mark_failed(profile_id, str(exc))
            raise

    job = queue.submit(Job(kind="voice-train", params={"profile_id": profile_id}), runner)
    return {"job_id": job.id, "profile_id": profile_id}


@app.on_event("shutdown")
def _shutdown() -> None:
    acestep_service.shutdown()
