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

import asyncio
import re
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from . import (
    acestep_service,
    applio_service,
    db,
    errorlog,
    keystore,
    mock_audio,
    settings,
    stems,
    system_info,
    text_provider,
    voice_service,
)
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


@app.exception_handler(Exception)
async def _log_unhandled(request: Request, exc: Exception) -> JSONResponse:
    # Genuine bugs (not the intentional HTTPExceptions, which have their own
    # handler) get recorded so the user can read them in Settings and report.
    errorlog.record(f"{request.method} {request.url.path}", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Something went wrong in the engine. See the error log in Settings."},
    )


@app.get("/ping")
def ping() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health")
def health() -> dict:
    # The paths let the UI show exactly where the engine is looking, so a
    # misplaced install is diagnosable from Settings instead of guesswork.
    return {
        "status": "ok",
        "mock": settings.MOCK,
        "acestep_installed": settings.acestep_python().exists(),
        "acestep_running": False if settings.MOCK else acestep_service.is_healthy(),
        "applio_installed": settings.applio_python().exists(),
        "data_root": str(settings.DATA_ROOT),
        "output_dir": str(settings.OUTPUT_DIR),
        "acestep_dir": str(settings.ACESTEP_DIR),
        "applio_dir": str(settings.APPLIO_DIR),
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
    # Steers the generated vocal's register before conversion, so the RVC step
    # starts from a voice in the right range. "male", "female", or "".
    gender: Literal["", "male", "female"] = ""


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
    return _with_unlock(db.create_profile(req.name, req.sample_rate, req.gender))


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


# --------------------------- compose ----------------------------

class ComposeRequest(BaseModel):
    prompt: str = Field(min_length=1)
    voice_profile_id: Optional[str] = None
    instrumental: bool = False
    duration: Optional[float] = Field(default=None, ge=10, le=600)
    thinking: bool = True
    lyrics: str = ""
    # Where the finished files land; empty means the engine's own output folder.
    output_dir: str = ""
    # Also save the separated stems (vocals + instrumental) next to the track.
    save_stems: bool = False
    # Sing with a generic voice in this register instead of a trained profile.
    # Ignored when a voice_profile_id is given (the profile's range wins).
    vocal_gender: Literal["", "male", "female"] = ""


@app.post("/compose")
async def compose(req: ComposeRequest) -> dict:
    profile = None
    if req.voice_profile_id:
        profile = db.get_profile(req.voice_profile_id)
        if profile is None:
            raise HTTPException(404, "No such voice profile")
        if not settings.MOCK and (
            profile["status"] != "ready" or not profile["model_path"] or not profile["index_path"]
        ):
            raise HTTPException(409, f"Voice '{profile['name']}' is not trained yet")

    # Fail fast on impossible asks, before any GPU time is spent.
    out_dir = Path(req.output_dir) if req.output_dir.strip() else settings.OUTPUT_DIR
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        probe = out_dir / ".cadence-write-test"
        probe.write_text("ok")
        probe.unlink()
    except OSError as exc:
        raise HTTPException(400, f"Can't save to '{out_dir}': {exc}") from exc
    if req.save_stems and not settings.MOCK and not stems.available():
        raise HTTPException(
            409,
            "Saving separate stems needs the voice backend (Applio with Demucs). "
            + settings.setup_hint(),
        )

    async def runner(job: Job) -> None:
        user_lyrics = "" if req.instrumental else req.lyrics.strip()
        job.update(
            status=JobStatus.GENERATING,
            detail="Preparing" if user_lyrics else "Writing lyrics",
        )
        try:
            structured = await asyncio.to_thread(
                text_provider.structure_prompt, req.prompt, req.instrumental
            )
        except text_provider.TextProviderError:
            # With user-supplied lyrics we only needed a style caption, so fall
            # back to the prompt rather than failing when no text provider is up.
            if not user_lyrics:
                raise
            structured = {"caption": req.prompt, "lyrics": "", "vocal_language": "en", "bpm": None}
        caption = structured["caption"] or req.prompt
        # Generate the base vocal in the target register — the profile's range
        # when converting (a cross-register conversion sounds strained), or the
        # requested generic voice when singing without a profile.
        gender = (profile or {}).get("gender", "") or req.vocal_gender
        if gender and not req.instrumental and f"{gender} vocal" not in caption.lower():
            caption = f"{caption}, {gender} vocals"
        lyrics = user_lyrics or structured["lyrics"]

        job.update(status=JobStatus.GENERATING, detail="Generating music")
        if settings.MOCK:
            music_path = str(settings.OUTPUT_DIR / f"track-music-{job.id}.wav")
            mock_audio.write_mock_track(Path(music_path), seconds=req.duration or 15)
        else:
            gen = await acestep_service.generate(
                {
                    "prompt": caption,
                    "lyrics": lyrics,
                    "vocal_language": structured["vocal_language"],
                    "bpm": structured["bpm"],
                    "audio_duration": req.duration,
                    "instrumental": req.instrumental,
                    "thinking": req.thinking,
                    "audio_format": "wav",
                },
                progress=lambda m: job.update(detail=m),
            )
            music_path = gen["audio_path"]

        final_path = music_path
        voice_name = None
        # Stems produced along the way, reused if the user asked to keep them.
        stem_vocal: Optional[Path] = None
        stem_instrumental: Optional[Path] = None
        if not req.instrumental and profile is not None:
            final = out_dir / f"track-{job.id}.wav"
            if settings.MOCK:
                job.update(status=JobStatus.CONVERTING, detail="Converting to your voice")
                mock_audio.write_mock_conversion(Path(music_path), final)
                final_path = str(final)
            elif stems.available():
                # Re-voice only the isolated vocal, then remix with the instrumental.
                job.update(status=JobStatus.CONVERTING, detail="Separating vocals")
                vocal, instrumental = await stems.separate(
                    Path(music_path), settings.OUTPUT_DIR / f"stems-{job.id}"
                )
                job.update(status=JobStatus.CONVERTING, detail="Converting to your voice")
                converted = settings.OUTPUT_DIR / f"vocal-{job.id}.wav"
                await applio_service.convert(
                    {
                        "input_path": str(vocal),
                        "output_path": str(converted),
                        "pth_path": profile["model_path"],
                        "index_path": profile["index_path"],
                    }
                )
                job.update(status=JobStatus.CONVERTING, detail="Remixing")
                await stems.remix(converted, instrumental, final)
                final_path = str(final)
                stem_vocal = converted
                stem_instrumental = instrumental
            else:
                # Fallback: convert the full mix (lower quality, but always works).
                job.update(status=JobStatus.CONVERTING, detail="Converting to your voice")
                conv = await applio_service.convert(
                    {
                        "input_path": music_path,
                        "output_path": str(final),
                        "pth_path": profile["model_path"],
                        "index_path": profile["index_path"],
                    }
                )
                final_path = conv["audio_path"]
            voice_name = profile["name"]

        # Deliver into the chosen folder, and keep the stems if asked.
        if req.output_dir.strip() and Path(final_path).parent != out_dir:
            delivered = out_dir / f"track-{job.id}.wav"
            shutil.copyfile(final_path, delivered)
            final_path = str(delivered)
        if req.save_stems:
            job.update(detail="Separating stems")
            v_out = out_dir / f"track-{job.id}.vocals.wav"
            i_out = out_dir / f"track-{job.id}.instrumental.wav"
            if settings.MOCK:
                mock_audio.write_mock_track(v_out, seconds=req.duration or 15)
                mock_audio.write_mock_track(i_out, seconds=req.duration or 15)
            else:
                if stem_vocal is None or stem_instrumental is None:
                    stem_vocal, stem_instrumental = await stems.separate(
                        Path(music_path), settings.OUTPUT_DIR / f"stems-{job.id}"
                    )
                shutil.copyfile(stem_vocal, v_out)
                shutil.copyfile(stem_instrumental, i_out)

        track = db.create_track(
            prompt=req.prompt,
            caption=caption,
            lyrics=lyrics,
            vocal_language=structured["vocal_language"],
            bpm=structured["bpm"],
            audio_path=final_path,
            voice_profile_id=profile["id"] if profile else None,
            voice_name=voice_name,
            instrumental=1 if req.instrumental else 0,
        )
        job.result = {"track": track}
        job.update(status=JobStatus.DONE, detail="Done")

    job = queue.submit(Job(kind="compose", params={"prompt": req.prompt}), runner)
    return {"job_id": job.id}


@app.get("/tracks")
def list_tracks() -> list[dict]:
    return db.list_tracks()


@app.delete("/tracks/{track_id}")
def delete_track(track_id: str) -> dict:
    track = db.get_track(track_id)
    if track:
        Path(track["audio_path"]).unlink(missing_ok=True)
        db.delete_track(track_id)
    return {"deleted": track_id}


@app.get("/tracks/{track_id}/audio")
def track_audio(track_id: str) -> FileResponse:
    track = db.get_track(track_id)
    if track is None:
        raise HTTPException(404, "No such track")
    path = Path(track["audio_path"])
    if not path.exists():
        raise HTTPException(410, "Track file no longer exists")
    return FileResponse(path, media_type="audio/wav", content_disposition_type="inline")


def _slug(text: Optional[str], fallback: str = "cadence-track") -> str:
    s = re.sub(r"[^\w\s-]", "", (text or "")).strip().lower()
    s = re.sub(r"[\s_-]+", "-", s)[:48].strip("-")
    return s or fallback


@app.get("/tracks/{track_id}/export")
def export_track(track_id: str, fmt: str = "wav") -> FileResponse:
    track = db.get_track(track_id)
    if track is None:
        raise HTTPException(404, "No such track")
    src = Path(track["audio_path"])
    if not src.exists():
        raise HTTPException(410, "Track file no longer exists")
    name = _slug(track.get("prompt") or track.get("caption"))

    if fmt == "mp3":
        mp3 = src.with_suffix(".mp3")
        if not mp3.exists():
            python = settings.applio_python()
            if not python.exists():
                raise HTTPException(503, "MP3 export needs the Applio environment")
            helper = Path(__file__).parent / "mp3_helper.py"
            proc = subprocess.run(
                [str(python), str(helper), str(src), str(mp3)],
                cwd=str(settings.APPLIO_DIR),
                capture_output=True, text=True, timeout=180,
            )
            if proc.returncode != 0 or not mp3.exists():
                raise HTTPException(500, f"MP3 export failed: {(proc.stderr or proc.stdout)[-300:]}")
        return FileResponse(mp3, media_type="audio/mpeg", filename=f"{name}.mp3")

    return FileResponse(src, media_type="audio/wav", filename=f"{name}.wav")


# ---------------------- settings & system -----------------------

class SettingsUpdate(BaseModel):
    text_provider: Optional[str] = None


class SecretUpdate(BaseModel):
    value: str = Field(min_length=1)


def _settings_payload() -> dict:
    return {
        "text_provider": db.get_setting("text_provider", "ollama"),
        "secrets": keystore.status(),
    }


@app.get("/settings")
def get_settings() -> dict:
    return _settings_payload()


@app.put("/settings")
def update_settings(req: SettingsUpdate) -> dict:
    if req.text_provider is not None:
        if req.text_provider not in ("ollama", "claude", "openai", "gemini"):
            raise HTTPException(422, "text_provider must be ollama, claude, openai, or gemini")
        db.set_setting("text_provider", req.text_provider)
    return _settings_payload()


@app.get("/secrets")
def get_secrets() -> dict:
    return keystore.status()


@app.put("/secrets/{name}")
def put_secret(name: str, req: SecretUpdate) -> dict:
    if name not in keystore.KNOWN:
        raise HTTPException(404, f"Unknown secret '{name}'")
    try:
        keystore.set_secret(name, req.value.strip())
    except keystore.KeyringUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    return keystore.status()


@app.delete("/secrets/{name}")
def delete_secret(name: str) -> dict:
    keystore.clear_secret(name)
    return keystore.status()


@app.get("/logs")
def get_logs() -> dict:
    """Recent errors, plus the folder they live in (for an Open button)."""
    return {"dir": str(settings.LOG_DIR), "text": errorlog.tail()}


@app.delete("/logs")
def clear_logs() -> dict:
    errorlog.clear()
    return {"ok": True}


@app.get("/system")
def system() -> dict:
    # tools: what the one-time backend setup script needs from the user's PATH.
    return {
        "gpu": system_info.gpu_status(),
        "ollama": system_info.ollama_status(),
        "tools": {
            "git": shutil.which("git") is not None,
            "uv": shutil.which("uv") is not None,
        },
    }


@app.on_event("shutdown")
def _shutdown() -> None:
    acestep_service.shutdown()
