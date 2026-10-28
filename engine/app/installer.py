"""One-click install of the AI backends, with step-by-step progress.

The same work as scripts/setup-backends.*, run inside the engine so the app can
show it: no terminal, no Git, and no uv to install first. It runs as a job on
the engine's queue, so the UI polls it like any other job and a generation can
never start halfway through an install.

Every step is safe to repeat: sources are only refetched when the pinned commit
changes, and `uv` is idempotent about environments, so a cancelled or failed
install resumes by running it again.
"""

from __future__ import annotations

import asyncio
import collections
import contextlib
import hashlib
import http.client
import os
import platform
import re
import shutil
import signal
import ssl
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Optional

from . import acestep_service, backends, settings, system_info
from .jobs import Job, JobStatus, queue

KIND = "install"

# (id, short label). The UI draws one segment per step.
STEPS = (
    ("check", "Check system"),
    ("uv", "Get uv"),
    ("music", "Music backend"),
    ("voice", "Voice backend"),
    ("models", "Music models"),
    ("verify", "Verify"),
)

# Written next to a source tree once it has been unpacked from an archive.
COMMIT_MARKER = ".cadence-commit"

_ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")


class InstallError(RuntimeError):
    """Something went wrong that the user can act on; the message is shown as-is."""


class InstallCancelled(Exception):
    pass


def _clean(text: str) -> str:
    return _ANSI.sub("", text).strip()


# ---------------------------------------------------------------- progress


class Progress:
    """What the UI shows for one install: steps, the live line, and a log tail."""

    def __init__(self, job: Job) -> None:
        self.job = job
        self.steps = [{"id": i, "label": label, "state": "pending", "note": ""} for i, label in STEPS]
        self.log: collections.deque[str] = collections.deque(maxlen=300)
        self.line = ""
        self.bytes: Optional[dict[str, Any]] = None
        self.started_at = time.time()
        self.finished_at: Optional[float] = None
        self.cancelled = False

    def _step(self, sid: str) -> dict[str, Any]:
        return next(s for s in self.steps if s["id"] == sid)

    def start(self, sid: str, title: str) -> None:
        self.check_cancel()
        self._step(sid)["state"] = "running"
        self.job.update(detail=title)
        self.say(f"==> {title}")

    def finish(self, sid: str, note: str = "") -> None:
        step = self._step(sid)
        step["state"] = "done"
        step["note"] = note

    def fail_current(self) -> None:
        for s in self.steps:
            if s["state"] == "running":
                s["state"] = "error"

    def cancel_current(self) -> None:
        self.cancelled = True
        for s in self.steps:
            if s["state"] == "running":
                s["state"] = "pending"

    def say(self, text: str) -> None:
        text = _clean(text)
        if text:
            self.log.append(text)
            self.line = text

    def live(self, text: str) -> None:
        """Update the headline without adding to the log (download counters)."""
        text = _clean(text)
        if text:
            self.line = text

    def check_cancel(self) -> None:
        if self.job.cancel_requested:
            raise InstallCancelled()

    def snapshot(self) -> dict[str, Any]:
        return {
            "steps": [dict(s) for s in self.steps],
            "line": self.line,
            "log": list(self.log),
            "bytes": self.bytes,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "cancelled": self.cancelled,
        }


# The child process to kill if the user cancels. Installs run one at a time.
_active: dict[str, Any] = {"proc": None}


def _kill_tree(proc: Any) -> None:
    if proc is None or proc.returncode is not None:
        return
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        else:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except Exception:  # noqa: BLE001 - it may already be gone
        pass


def request_cancel(job: Job) -> None:
    job.cancel_requested = True
    _kill_tree(_active["proc"])


def _install_jobs() -> list[Job]:
    return [j for j in queue.all() if j.kind == KIND]  # newest first


def active_job() -> Optional[Job]:
    return next(
        (j for j in _install_jobs() if j.status in (JobStatus.QUEUED, JobStatus.INSTALLING)),
        None,
    )


def latest_job() -> Optional[Job]:
    jobs = _install_jobs()
    return jobs[0] if jobs else None


def acestep_models_present() -> bool:
    return (settings.ACESTEP_DIR / "checkpoints" / "acestep-v15-turbo" / "model.safetensors").is_file()


# ---------------------------------------------------------------- helpers


def _tool_env() -> dict[str, str]:
    env = os.environ.copy()
    for stale in ("VIRTUAL_ENV", "PYTHONHOME", "PYTHONPATH"):
        env.pop(stale, None)  # would point uv and the pythons it starts at the engine's own
    env.update(
        UV_CACHE_DIR=str(settings.TOOLS_DIR / "uv-cache"),
        UV_PYTHON_INSTALL_DIR=str(settings.TOOLS_DIR / "python"),
        NO_COLOR="1",
        PYTHONUNBUFFERED="1",
        # Child output is piped, so Python would pick the legacy code page and
        # choke on tqdm's progress-bar glyphs.
        PYTHONIOENCODING="utf-8",
        PYTHONUTF8="1",
    )
    return env


async def _run(p: Progress, cmd: list[str], cwd: Optional[Path], env: dict[str, str], what: str) -> list[str]:
    """Run a command, streaming its output into the log. Returns the lines it printed."""
    p.say("$ " + " ".join(cmd))
    kwargs: dict[str, Any] = {}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    else:
        kwargs["start_new_session"] = True  # so cancel can kill the whole group
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(cwd) if cwd else None,
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        **kwargs,
    )
    _active["proc"] = proc
    lines: collections.deque[str] = collections.deque(maxlen=200)

    def take(raw: bytes) -> None:
        text = _clean(raw.decode("utf-8", errors="replace"))
        if not text:
            return
        lines.append(text)
        # tqdm-style bars redraw the same line; keep them out of the log.
        (p.live if "%|" in text else p.say)(text)

    try:
        assert proc.stdout is not None
        buf = b""
        while True:
            chunk = await proc.stdout.read(4096)
            if not chunk:
                break
            *done, buf = re.split(rb"[\r\n]", buf + chunk)
            for raw in done:
                take(raw)
        take(buf)
        code = await proc.wait()
    finally:
        _active["proc"] = None
    p.check_cancel()
    if code != 0:
        raise InstallError(f"{what} failed (exit code {code}).\n" + "\n".join(list(lines)[-12:]))
    return list(lines)


def _ssl_context() -> ssl.SSLContext:
    """The system's trusted roots, plus certifi's.

    Windows fetches root certificates lazily, and Python only sees the ones
    already in the store. So it can intermittently reject GitHub with "unable to
    get issuer certificate" while a browser is happy. certifi's roots cover that
    gap; keeping the system store as well means roots a company has installed
    still work.
    """
    ctx = ssl.create_default_context()
    with contextlib.suppress(ImportError, OSError):
        import certifi

        ctx.load_verify_locations(cafile=certifi.where())
    return ctx


def _download(url: str, dest: Path, p: Progress, label: str, sha256: Optional[str] = None) -> None:
    """Fetch url to dest through a .part file, checking its hash when one is known."""
    part = dest.with_suffix(dest.suffix + ".part")
    last: Optional[BaseException] = None
    for attempt in range(1, 4):
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            req = urllib.request.Request(url, headers={"User-Agent": "Cadence-installer"})
            digest = hashlib.sha256()
            done = 0
            with urllib.request.urlopen(req, timeout=60, context=_ssl_context()) as resp, open(part, "wb") as fh:
                total = int(resp.headers.get("Content-Length") or 0) or None
                while True:
                    chunk = resp.read(1 << 20)
                    if not chunk:
                        break
                    p.check_cancel()
                    fh.write(chunk)
                    digest.update(chunk)
                    done += len(chunk)
                    p.bytes = {"done": done, "total": total}
                    of = f" of {total / 1e6:.0f} MB" if total else ""
                    p.live(f"Downloading {label}: {done / 1e6:.0f} MB{of}")
            if sha256 and digest.hexdigest() != sha256:
                part.unlink(missing_ok=True)
                raise InstallError(
                    f"The download of {label} didn't match its published checksum, so Cadence "
                    "won't run it. Try again; if it keeps happening, your network may be altering downloads."
                )
            part.replace(dest)
            p.bytes = None
            return
        except (InstallCancelled, InstallError):
            p.bytes = None
            part.unlink(missing_ok=True)
            raise
        except urllib.error.HTTPError as exc:
            p.bytes = None
            part.unlink(missing_ok=True)
            if 400 <= exc.code < 500:  # the pinned URL is wrong; trying again won't change that
                raise InstallError(f"Couldn't download {label}: the server answered {exc.code} {exc.reason} for {url}") from exc
            last = exc
            p.say(f"Download of {label} failed on attempt {attempt}: {exc}")
            if attempt < 3:
                time.sleep(2 * attempt)
        except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.HTTPException) as exc:
            last = exc  # network trouble: worth another go
            p.say(f"Download of {label} failed on attempt {attempt}: {exc}")
            if attempt < 3:
                time.sleep(2 * attempt)
        except OSError as exc:  # our own disk (full, read-only, bad path), not the network
            p.bytes = None
            part.unlink(missing_ok=True)
            raise InstallError(f"Couldn't save {label} to {dest.parent}: {exc}") from exc
    p.bytes = None
    part.unlink(missing_ok=True)
    raise InstallError(
        f"Couldn't download {label}. Check your internet connection and try again.\n({last})"
    )


def _extract_one(archive: Path, basename: str, dest: Path) -> None:
    """Write the one file called basename out of a .zip or .tar.gz (uv ships as either)."""
    data: Optional[bytes] = None
    if archive.suffix == ".zip":
        with zipfile.ZipFile(archive) as zf:
            member = next((n for n in zf.namelist() if Path(n).name == basename), None)
            if member:
                data = zf.read(member)
    else:
        with tarfile.open(archive) as tf:
            for m in tf:
                if m.isfile() and Path(m.name).name == basename:
                    f = tf.extractfile(m)
                    data = f.read() if f else None
                    break
    if data is None:
        raise InstallError(f"The uv download didn't contain {basename}.")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    if os.name != "nt":
        dest.chmod(0o755)


def _safe_extract_zip(archive: Path, dest: Path) -> None:
    root = dest.resolve()
    with zipfile.ZipFile(archive) as zf:
        for name in zf.namelist():
            target = (dest / name).resolve()
            if target != root and root not in target.parents:
                raise InstallError("A downloaded archive contained an unsafe path, so it was not unpacked.")
        zf.extractall(dest)


def _installed_commit(dest: Path) -> Optional[str]:
    """The commit a source folder is at: our marker, else a git checkout's HEAD."""
    marker = dest / COMMIT_MARKER
    if marker.is_file():
        return marker.read_text(encoding="utf-8").strip() or None
    head = dest / ".git" / "HEAD"
    if head.is_file():
        text = head.read_text(encoding="utf-8").strip()
        if re.fullmatch(r"[0-9a-f]{40}", text):  # detached HEAD, as setup-backends leaves it
            return text
    return None


def _unpack_over(archive: Path, dest: Path, scratch: Path) -> None:
    """Unpack a GitHub archive and lay it over dest, leaving what isn't in it alone.

    Overlaying (not replacing) matters: dest may already hold a built .venv, the
    model weights, and Applio's trained voices.
    """
    out = scratch / "unpacked"
    _safe_extract_zip(archive, out)
    tops = [d for d in out.iterdir() if d.is_dir()]
    if len(tops) != 1:
        raise InstallError("The downloaded source wasn't laid out as expected.")
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copytree(tops[0], dest, dirs_exist_ok=True)


def _dir_bytes(path: Path) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            with contextlib.suppress(OSError):
                total += os.path.getsize(os.path.join(root, name))
    return total


async def _until_cancelled(coro: Any, p: Progress) -> Any:
    """Await coro, but stop it promptly if the user cancels."""
    task = asyncio.ensure_future(coro)
    try:
        while True:
            done, _ = await asyncio.wait({task}, timeout=0.5)
            if done:
                return task.result()
            if p.job.cancel_requested:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await task
                raise InstallCancelled()
    except asyncio.CancelledError:
        task.cancel()
        raise


# ------------------------------------------------------------------ steps


def _check_system(p: Progress) -> None:
    settings.ACESTEP_DIR.parent.mkdir(parents=True, exist_ok=True)
    settings.TOOLS_DIR.mkdir(parents=True, exist_ok=True)
    free_gb = shutil.disk_usage(settings.ACESTEP_DIR.parent).free / 1e9
    p.say(f"Free space where Cadence installs: {free_gb:.0f} GB")
    if free_gb < backends.DISK_NEEDED_GB:
        raise InstallError(
            f"Cadence needs about {backends.DISK_NEEDED_GB} GB free to install the AI models, and "
            f"this drive has {free_gb:.0f} GB. Free up some space, or point Cadence at a bigger "
            "drive under Settings > Storage, then try again."
        )
    gpu = system_info.gpu_status()
    if gpu.get("cuda"):
        vram = gpu.get("vram_total_mb")
        extra = f" ({vram / 1024:.0f} GB)" if vram else ""
        p.say(f"GPU: {gpu['device']}{extra}")
    elif gpu.get("mps"):
        p.say(f"GPU: {gpu['device']}")
    else:
        p.say(
            "No NVIDIA GPU found. Cadence will still install, but making music will be very "
            "slow without one."
        )
    if os.name != "nt" and not shutil.which("ffmpeg"):
        p.say("Note: ffmpeg wasn't found. Install it (brew install ffmpeg, or apt install ffmpeg) before training a voice.")


async def _ensure_uv(p: Progress) -> tuple[str, str]:
    """Return (path to uv, note). Uses an existing uv, else downloads the pinned one."""
    found = shutil.which("uv")
    if found:
        p.say(f"Using uv at {found}")
        return found, "Already installed"
    exe = settings.TOOLS_DIR / ("uv.exe" if os.name == "nt" else "uv")
    if exe.is_file():
        p.say(f"Using the uv Cadence downloaded earlier: {exe}")
        return str(exe), "Already downloaded"
    entry = backends.UV_ARCHIVES.get((sys.platform, platform.machine().lower()))
    if entry is None:
        raise InstallError(
            "There's no ready-made uv for this system. Install uv yourself "
            "(https://docs.astral.sh/uv/getting-started/installation/) and click Install again."
        )
    name, sha = entry
    url = backends.UV_URL.format(version=backends.UV_VERSION, name=name)
    archive = settings.TOOLS_DIR / name
    await asyncio.to_thread(_download, url, archive, p, f"uv {backends.UV_VERSION}", sha)
    try:
        await asyncio.to_thread(_extract_one, archive, exe.name, exe)
    finally:
        archive.unlink(missing_ok=True)
    await _run(p, [str(exe), "--version"], None, os.environ.copy(), "uv")
    return str(exe), f"Downloaded {backends.UV_VERSION}"


async def _ensure_source(p: Progress, src: backends.Source, dest: Path) -> None:
    if _installed_commit(dest) == src.commit:
        p.say(f"{src.folder} source is already at {src.commit[:8]}")
        return
    p.say(f"Downloading {src.folder} ({src.commit[:8]})")
    settings.TOOLS_DIR.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="cadence-src-", dir=settings.TOOLS_DIR))
    try:
        archive = scratch / "source.zip"
        await asyncio.to_thread(_download, src.archive_url, archive, p, src.folder)
        p.say(f"Unpacking {src.folder}")
        await asyncio.to_thread(_unpack_over, archive, dest, scratch)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    (dest / COMMIT_MARKER).write_text(src.commit, encoding="utf-8")


async def _install_music(p: Progress, uv: str, env: dict[str, str]) -> None:
    dest = settings.ACESTEP_DIR
    await _ensure_source(p, backends.ACESTEP, dest)
    p.say("Building the music environment. This pulls PyTorch, a few GB, so it takes a while.")
    await _run(p, [uv, "sync"], dest, env, "Building the music environment")


async def _install_voice(p: Progress, uv: str, env: dict[str, str]) -> None:
    dest = settings.APPLIO_DIR
    await _ensure_source(p, backends.APPLIO, dest)
    py = settings.applio_python()
    if not py.exists():
        p.say("Creating the voice environment (Python 3.12)")
        await _run(p, [uv, "venv", "--python", "3.12", ".venv"], dest, env, "Creating the voice environment")
    p.say("Installing the voice packages. This pulls PyTorch, a few GB.")
    cmd = [uv, "pip", "install", "--python", str(py), "-r", "requirements.txt"]
    if sys.platform != "darwin":
        cmd += ["--extra-index-url", backends.TORCH_INDEX, "--index-strategy", "unsafe-best-match"]
    await _run(p, cmd, dest, env, "Installing the voice packages")
    p.say("Installing Demucs (vocal separation)")
    await _run(p, [uv, "pip", "install", "--python", str(py), "demucs"], dest, env, "Installing Demucs")
    # Applio never fetches these on its own: the pitch models and pretrained
    # voices load from fixed paths, so training and conversion fail without them.
    p.say("Downloading the voice assets: pitch models, pretrained voices (about 1.2 GB)")
    await _run(
        p,
        [str(py), "core.py", "prerequisites", "--pretraineds_hifigan", "True", "--models", "True", "--exe", "True"],
        dest,
        env,
        "Downloading the voice assets",
    )


async def _install_models(p: Progress) -> str:
    """Make the music server download its model files now, not during the first song.

    A healthy server proves nothing here: by default ACE-Step answers /health at
    once and loads (so downloads) its models on the first request. So this asks
    for the models to load at startup, and then checks the files are on disk.
    """
    if acestep_models_present():
        p.say("The music models are already on disk.")
        return "Already downloaded"
    if await asyncio.to_thread(acestep_service.is_healthy):
        # Up, but with nothing loaded: restart it so that startup does the download.
        if not acestep_service.owns_server():
            raise InstallError(
                f"A music server that Cadence didn't start is already running on port "
                f"{settings.ACESTEP_PORT}. Close it and try again."
            )
        p.say("Restarting the music server so it loads its models.")
        acestep_service.shutdown()
        for _ in range(40):
            if not await asyncio.to_thread(acestep_service.is_healthy):
                break
            await asyncio.sleep(0.5)
    ckpt = settings.ACESTEP_DIR / "checkpoints"
    p.say("Starting the music model. The first start downloads its model files, several GB.")
    status = {"text": "Starting the music model"}

    async def watch() -> None:
        while True:
            n = await asyncio.to_thread(_dir_bytes, ckpt)
            p.bytes = {"done": n, "total": None}
            p.live(f"{status['text']} - {n / 1e9:.1f} GB of model files on disk")
            await asyncio.sleep(2)

    watcher = asyncio.ensure_future(watch())
    try:
        await _until_cancelled(
            acestep_service.ensure_running(
                lambda m: status.__setitem__("text", m), preload_models=True
            ),
            p,
        )
    except acestep_service.AceStepError as exc:
        raise InstallError(f"The music model didn't start.\n{exc}") from exc
    finally:
        watcher.cancel()
        p.bytes = None
        acestep_service.shutdown()  # only ever stops a server this engine started
    if not acestep_models_present():
        tail = acestep_service.server_log_tail()
        raise InstallError(
            "The music server started, but its model files aren't on disk."
            + (f"\n{tail}" if tail else "")
        )
    p.say("The music models downloaded and loaded cleanly.")
    return ""


async def _verify(p: Progress, env: dict[str, str]) -> None:
    for label, py in (("music", settings.acestep_python()), ("voice", settings.applio_python())):
        if not py.exists():
            raise InstallError(f"The {label} environment is missing its Python ({py}). Try again.")
    await _run(
        p,
        [str(settings.applio_python()), "-c",
         "import torch, demucs; print('torch', torch.__version__, 'cuda', torch.cuda.is_available())"],
        settings.APPLIO_DIR,
        env,
        "Checking the voice environment",
    )
    needed = [
        "rvc/models/predictors/rmvpe.pt",
        "rvc/models/embedders/contentvec/pytorch_model.bin",
        "rvc/models/pretraineds/hifi-gan/f0G40k.pth",
    ]
    if os.name == "nt":
        needed.append("ffmpeg.exe")
    missing = [rel for rel in needed if not (settings.APPLIO_DIR / rel).is_file()]
    if missing:
        raise InstallError("Some voice files are missing: " + ", ".join(missing) + ". Try again.")
    p.say("Everything checks out.")


async def _install(p: Progress) -> None:
    p.start("check", "Checking your system")
    await asyncio.to_thread(_check_system, p)
    p.finish("check")

    p.start("uv", "Getting uv (Python package manager)")
    uv, note = await _ensure_uv(p)
    p.finish("uv", note)
    env = _tool_env()

    p.start("music", "Installing the music backend (ACE-Step)")
    await _install_music(p, uv, env)
    p.finish("music")

    p.start("voice", "Installing the voice backend (Applio + Demucs)")
    await _install_voice(p, uv, env)
    p.finish("voice")

    p.start("models", "Downloading the music models")
    note = await _install_models(p)
    p.finish("models", note)

    p.start("verify", "Verifying the install")
    await _verify(p, env)
    p.finish("verify")


# --------------------------------------------------------------- simulation


def _simulating() -> bool:
    """Mock mode, or CADENCE_MOCK_INSTALL=1 to try the screen without installing 18 GB."""
    return settings.MOCK or os.getenv("CADENCE_MOCK_INSTALL") == "1"


_SCRIPT = {
    "check": ["Free space where Cadence installs: 407 GB", "GPU: NVIDIA GeForce RTX 3080 (10 GB)"],
    "uv": ["Using uv at C:\\tools\\uv.exe"],
    "music": [
        "Downloading ACE-Step-1.5 (6d467e4b)",
        "Unpacking ACE-Step-1.5",
        "Resolved 212 packages in 1.4s",
        "Downloading torch (2.8GiB)",
        "Installed 212 packages in 41s",
    ],
    "voice": [
        "Downloading Applio (178c86a4)",
        "Creating the voice environment (Python 3.12)",
        "Installed 148 packages in 33s",
        "Installing Demucs (vocal separation)",
        "Downloading the voice assets: pitch models, pretrained voices",
    ],
    "models": ["Starting the music model", "4.2 GB of model files on disk", "8.9 GB of model files on disk"],
    "verify": ["torch 2.8.0+cu128 cuda True", "Everything checks out."],
}


async def _simulate(p: Progress) -> None:
    delay = float(os.getenv("CADENCE_MOCK_INSTALL_DELAY", "0.6"))
    fail = os.getenv("CADENCE_MOCK_INSTALL_FAIL", "")
    for sid, label in STEPS:
        p.start(sid, label)
        for n, line in enumerate(_SCRIPT[sid]):
            for _ in range(max(1, int(delay / 0.1))):  # sleep in slices so cancel is prompt
                await asyncio.sleep(0.1)
                p.check_cancel()
            if fail == sid and n == 1:
                raise InstallError(
                    f"Simulated failure while working on: {label}.\n"
                    "error: Failed to download `torch==2.8.0+cu128`\n  Caused by: connection reset"
                )
            p.say(line)
        p.finish(sid, "Already installed" if sid == "uv" else "")


# ------------------------------------------------------------------- entry


async def run_install(job: Job) -> None:
    p = Progress(job)
    job.progress_fn = p.snapshot
    job.update(status=JobStatus.INSTALLING, detail="Installing")
    try:
        p.check_cancel()
        await (_simulate(p) if _simulating() else _install(p))
        job.result = {"installed": True}
        job.update(status=JobStatus.DONE, detail="Installed")
    except InstallCancelled:
        p.cancel_current()
        p.say("Cancelled. Click Install again to pick up where it left off.")
        job.error = "Cancelled"
        job.update(status=JobStatus.ERROR, detail="Cancelled")
    except BaseException:
        p.fail_current()
        raise
    finally:
        p.finished_at = time.time()
        _active["proc"] = None
