"""Install verification: the in-app installer's parts, without installing 18 GB.

  1. The commits pinned in setup-backends.ps1 / .sh match engine/app/backends.py.
  2. The helpers: safe unpacking, checksum-verified downloads, commit detection.
  3. A simulated install over HTTP: success, joining a running install, cancel,
     and a failure partway through. Each runs against its own engine process.

Usage, from engine/ so uv uses the engine's environment:

    uv run python ../scripts/verify_install.py [--network]

--network also downloads the real pinned uv and checks it (about 20 MB).
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import http.server
import io
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import traceback
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENGINE = ROOT / "engine"

# The helpers read settings at import, so point them at scratch space first.
_SCRATCH = Path(tempfile.mkdtemp(prefix="cadence-verify-install-"))
os.environ.update(
    CADENCE_TOOLS_DIR=str(_SCRATCH / "tools"),
    CADENCE_ACESTEP_DIR=str(_SCRATCH / "ace"),
    CADENCE_APPLIO_DIR=str(_SCRATCH / "applio"),
    CADENCE_DB_PATH=str(_SCRATCH / "helpers.db"),
    CADENCE_LOG_DIR=str(_SCRATCH / "logs"),
)
sys.path.insert(0, str(ENGINE))

from app import backends, installer, settings  # noqa: E402
from app.jobs import Job  # noqa: E402


def new_progress() -> installer.Progress:
    return installer.Progress(Job(kind="install", params={}))


# ------------------------------------------------------------------ helpers


def test_pins_match_scripts() -> None:
    ps1 = (ROOT / "scripts" / "setup-backends.ps1").read_text(encoding="utf-8")
    sh = (ROOT / "scripts" / "setup-backends.sh").read_text(encoding="utf-8")
    for src, ps_var, sh_var in (
        (backends.ACESTEP, "AceCommit", "ace_commit"),
        (backends.APPLIO, "ApplioCommit", "applio_commit"),
    ):
        in_ps = re.search(rf'\${ps_var}\s*=\s*"([0-9a-f]{{40}})"', ps1)
        in_sh = re.search(rf'{sh_var}="([0-9a-f]{{40}})"', sh)
        assert in_ps and in_sh, f"couldn't find the {src.folder} pin in both scripts"
        assert in_ps.group(1) == src.commit, f"{src.folder}: setup-backends.ps1 differs from backends.py"
        assert in_sh.group(1) == src.commit, f"{src.folder}: setup-backends.sh differs from backends.py"


def test_clean_strips_terminal_codes() -> None:
    assert installer._clean("\x1b[31mred\x1b[0m   ") == "red"
    assert installer._clean("\x1b[1;32m  ok\x1b[K") == "ok"


def test_tls_trusts_certifi_as_well_as_the_system_store() -> None:
    import certifi
    import ssl

    only_certifi = ssl.create_default_context(cafile=certifi.where())
    ours = installer._ssl_context()
    assert len(ours.get_ca_certs()) >= len(only_certifi.get_ca_certs()) > 0, (
        "the installer's TLS context is missing certifi's roots"
    )


def test_unpack_rejects_zip_slip() -> None:
    d = Path(tempfile.mkdtemp(dir=_SCRATCH))
    archive = d / "evil.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("repo-1/ok.txt", "fine")
        zf.writestr("../escaped.txt", "nope")
    try:
        installer._safe_extract_zip(archive, d / "out")
    except installer.InstallError:
        assert not (d / "escaped.txt").exists(), "the escaping file was written anyway"
        return
    raise AssertionError("an archive with a ../ entry was accepted")


def test_unpack_overlays_without_deleting() -> None:
    d = Path(tempfile.mkdtemp(dir=_SCRATCH))
    archive = d / "src.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("repo-abc/a.txt", "new a")
        zf.writestr("repo-abc/sub/b.txt", "new b")
    dest = d / "dest"
    (dest / ".venv").mkdir(parents=True)
    (dest / ".venv" / "python").write_text("built env")
    (dest / "checkpoints").mkdir()
    (dest / "checkpoints" / "model.bin").write_text("11 GB of weights")
    (dest / "logs" / "myvoice").mkdir(parents=True)
    (dest / "logs" / "myvoice" / "trained.pth").write_text("a trained voice")
    (dest / "a.txt").write_text("old a")

    installer._unpack_over(archive, dest, d)

    assert (dest / "a.txt").read_text() == "new a", "tracked file wasn't refreshed"
    assert (dest / "sub" / "b.txt").read_text() == "new b"
    assert (dest / ".venv" / "python").read_text() == "built env", "the environment was lost"
    assert (dest / "checkpoints" / "model.bin").exists(), "model weights were lost"
    assert (dest / "logs" / "myvoice" / "trained.pth").exists(), "a trained voice was lost"


def test_installed_commit_detection() -> None:
    d = Path(tempfile.mkdtemp(dir=_SCRATCH))
    sha = "a" * 40
    assert installer._installed_commit(d) is None
    (d / ".git").mkdir()
    (d / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
    assert installer._installed_commit(d) is None, "a branch ref isn't a pinned commit"
    (d / ".git" / "HEAD").write_text(sha + "\n")
    assert installer._installed_commit(d) == sha, "a detached git checkout should count"
    (d / installer.COMMIT_MARKER).write_text("b" * 40)
    assert installer._installed_commit(d) == "b" * 40, "our marker should win"


def test_models_step_does_not_trust_a_healthy_server() -> None:
    """ACE-Step answers /health before it has downloaded anything. A real install
    once reported success having fetched nothing; the step must check the files."""
    svc = installer.acestep_service
    saved = (settings.ACESTEP_DIR, svc.is_healthy, svc.owns_server, svc.ensure_running, svc.shutdown)
    ace = Path(tempfile.mkdtemp(dir=_SCRATCH))
    settings.ACESTEP_DIR = ace
    seen: dict = {"preload": None, "shutdowns": 0, "up": False}

    async def fake_ensure(progress=None, preload_models=False):
        seen["preload"] = preload_models  # comes up "healthy" and downloads nothing

    def fake_shutdown():
        seen["shutdowns"] += 1
        seen["up"] = False

    svc.is_healthy = lambda: seen["up"]
    svc.owns_server = lambda: True
    svc.ensure_running = fake_ensure
    svc.shutdown = fake_shutdown
    try:
        # No weights, and a server that "starts" without fetching them: not a success.
        try:
            asyncio.run(installer._install_models(new_progress()))
        except installer.InstallError as exc:
            assert "aren't on disk" in str(exc), str(exc)
        else:
            raise AssertionError("a start that downloaded nothing was accepted")
        assert seen["preload"] is True, "startup wasn't asked to load the models"

        # A server of ours already up, lazily, with nothing loaded: restart it.
        seen.update(preload=None, shutdowns=0, up=True)
        try:
            asyncio.run(installer._install_models(new_progress()))
        except installer.InstallError:
            pass
        assert seen["shutdowns"] >= 1 and seen["preload"] is True, "a lazy server wasn't restarted"

        # Somebody else's server on the port: say so rather than skipping the download.
        seen.update(preload=None, up=True)
        svc.owns_server = lambda: False
        try:
            asyncio.run(installer._install_models(new_progress()))
        except installer.InstallError as exc:
            assert "didn't start" in str(exc), str(exc)
        else:
            raise AssertionError("a foreign server was treated as the music backend")
        assert seen["preload"] is None, "it tried to start a second server"

        # Weights already on disk: nothing to do, and no server is started.
        model = ace / "checkpoints" / "acestep-v15-turbo" / "model.safetensors"
        model.parent.mkdir(parents=True)
        model.write_bytes(b"weights")
        seen.update(preload=None, up=False)
        assert asyncio.run(installer._install_models(new_progress())) == "Already downloaded"
        assert seen["preload"] is None, "a server was started although the models were there"
    finally:
        settings.ACESTEP_DIR, svc.is_healthy, svc.owns_server, svc.ensure_running, svc.shutdown = saved


@contextlib.contextmanager
def file_server(files: dict[str, bytes]):
    root = Path(tempfile.mkdtemp(dir=_SCRATCH))
    for name, data in files.items():
        (root / name).write_bytes(data)

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(root), **kw)

        def log_message(self, *a):
            pass

    class QuietServer(http.server.ThreadingHTTPServer):
        def handle_error(self, request, client_address):
            pass  # the cancel test hangs up mid-download on purpose

    server = QuietServer(("127.0.0.1", 0), Quiet)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()


def test_download_checks_the_hash() -> None:
    import hashlib

    blob = os.urandom(3 * 1024 * 1024 + 17)
    good = hashlib.sha256(blob).hexdigest()
    with file_server({"blob.bin": blob}) as base:
        d = Path(tempfile.mkdtemp(dir=_SCRATCH))
        installer._download(f"{base}/blob.bin", d / "ok.bin", new_progress(), "blob", good)
        assert (d / "ok.bin").read_bytes() == blob
        assert not list(d.glob("*.part")), "a .part file was left behind"

        try:
            installer._download(f"{base}/blob.bin", d / "bad.bin", new_progress(), "blob", "0" * 64)
        except installer.InstallError as exc:
            assert "checksum" in str(exc)
            assert not (d / "bad.bin").exists(), "a file that failed its checksum was kept"
            assert not list(d.glob("*.part"))
            return
        raise AssertionError("a wrong checksum was accepted")


def test_download_failure_is_friendly_and_cancel_is_prompt() -> None:
    d = Path(tempfile.mkdtemp(dir=_SCRATCH))
    real_sleep = installer.time.sleep
    installer.time.sleep = lambda s: None  # don't wait out the retry backoff
    try:
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            dead = s.getsockname()[1]  # nothing is listening here
        try:
            installer._download(f"http://127.0.0.1:{dead}/x", d / "x", new_progress(), "thing")
        except installer.InstallError as exc:
            assert "internet connection" in str(exc), str(exc)
        else:
            raise AssertionError("an unreachable URL didn't fail")
    finally:
        installer.time.sleep = real_sleep

    with file_server({"big.bin": b"x" * (4 * 1024 * 1024)}) as base:
        p = new_progress()
        p.job.cancel_requested = True
        try:
            installer._download(f"{base}/big.bin", d / "big.bin", p, "big")
        except installer.InstallCancelled:
            assert not list(d.glob("big.bin*")), "a cancelled download left files behind"
            return
        raise AssertionError("a cancelled download kept going")


def test_download_errors_are_described_honestly() -> None:
    d = Path(tempfile.mkdtemp(dir=_SCRATCH))
    with file_server({"real.bin": b"payload"}) as base:
        # The destination folder doesn't have to exist yet.
        installer._download(f"{base}/real.bin", d / "not" / "yet" / "there.bin", new_progress(), "real")
        assert (d / "not" / "yet" / "there.bin").read_bytes() == b"payload"

        # A 404 means the pinned URL is wrong: say so at once, don't retry it.
        started = time.time()
        try:
            installer._download(f"{base}/missing.bin", d / "m.bin", new_progress(), "missing")
        except installer.InstallError as exc:
            assert "404" in str(exc), str(exc)
            assert "internet" not in str(exc), "a 404 isn't a connectivity problem"
            assert time.time() - started < 3, "a 404 was retried"
        else:
            raise AssertionError("a 404 didn't fail")

        # A local disk problem isn't the network's fault either.
        blocker = d / "blocker"
        blocker.write_text("a file where a folder should be")
        try:
            installer._download(f"{base}/real.bin", blocker / "x.bin", new_progress(), "real")
        except installer.InstallError as exc:
            assert "internet" not in str(exc), "a disk error was blamed on the internet: " + str(exc)
            assert "Couldn't save" in str(exc), str(exc)
        else:
            raise AssertionError("writing under a file didn't fail")


def test_extract_one_from_zip_and_tar() -> None:
    d = Path(tempfile.mkdtemp(dir=_SCRATCH))
    zpath = d / "uv.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("uvx.exe", "wrong one")
        zf.writestr("uv.exe", "windows uv")
    installer._extract_one(zpath, "uv.exe", d / "out" / "uv.exe")
    assert (d / "out" / "uv.exe").read_text() == "windows uv"

    tpath = d / "uv.tar.gz"
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for name, body in (("uv-x86_64/uvx", b"wrong one"), ("uv-x86_64/uv", b"posix uv")):
            info = tarfile.TarInfo(name)
            info.size = len(body)
            tf.addfile(info, io.BytesIO(body))
    tpath.write_bytes(buf.getvalue())
    installer._extract_one(tpath, "uv", d / "out2" / "uv")
    assert (d / "out2" / "uv").read_bytes() == b"posix uv"

    try:
        installer._extract_one(zpath, "missing.exe", d / "nope")
    except installer.InstallError:
        return
    raise AssertionError("a missing binary wasn't reported")


def test_real_uv_download() -> None:
    """Network: fetch the pinned uv, verify it against its published hash, run it."""
    real_which = shutil.which
    shutil.which = lambda name, *a, **kw: None if name == "uv" else real_which(name, *a, **kw)
    try:
        p = new_progress()
        path, note = asyncio.run(installer._ensure_uv(p))
    finally:
        shutil.which = real_which
    assert Path(path).is_file(), path
    out = subprocess.run([path, "--version"], capture_output=True, text=True).stdout
    assert backends.UV_VERSION in out, out
    assert note.startswith("Downloaded"), note


# --------------------------------------------------- a simulated install, live


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@contextlib.contextmanager
def engine(**extra_env: str):
    """A throwaway engine whose installs are simulated. Yields a request function."""
    port = _free_port()
    tmp = Path(tempfile.mkdtemp(dir=_SCRATCH))
    env = os.environ.copy()
    env.update(
        CADENCE_MOCK="1",
        CADENCE_PORT=str(port),
        CADENCE_DB_PATH=str(tmp / "db.sqlite"),
        CADENCE_LOG_DIR=str(tmp / "logs"),
        CADENCE_OUTPUT_DIR=str(tmp / "out"),
        CADENCE_TOOLS_DIR=str(tmp / "tools"),
        CADENCE_ACESTEP_DIR=str(tmp / "ace"),
        CADENCE_APPLIO_DIR=str(tmp / "applio"),
        **extra_env,
    )
    log = open(tmp / "engine.log", "wb")
    proc = subprocess.Popen([sys.executable, "run_engine.py"], cwd=ENGINE, env=env, stdout=log, stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{port}"

    def call(method: str, path: str, expect_error: bool = False):
        req = urllib.request.Request(base + path, method=method, data=b"" if method == "POST" else None)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.status, json.loads(resp.read().decode() or "null")
        except urllib.error.HTTPError as exc:
            if not expect_error:
                raise
            return exc.code, json.loads(exc.read().decode() or "null")

    try:
        for _ in range(80):
            if proc.poll() is not None:
                raise AssertionError("the test engine exited during startup:\n" + (tmp / "engine.log").read_text(errors="replace")[-800:])
            try:
                call("GET", "/health")
                break
            except Exception:
                time.sleep(0.5)
        else:
            raise AssertionError("the test engine never answered /health")
        yield call
    finally:
        proc.terminate()
        with contextlib.suppress(Exception):
            proc.wait(timeout=10)
        log.close()


def wait_for(call, job_id: str, until, seconds: float = 60) -> dict:
    end = time.time() + seconds
    while time.time() < end:
        _, job = call("GET", f"/status/{job_id}")
        if until(job):
            return job
        time.sleep(0.15)
    raise AssertionError(f"timed out waiting on the install job (last: {job['status']} / {job['detail']})")


def states(job: dict) -> dict[str, str]:
    return {s["id"]: s["state"] for s in job["progress"]["steps"]}


def test_simulated_install_succeeds() -> None:
    with engine(CADENCE_MOCK_INSTALL_DELAY="0.1") as call:
        _, health = call("GET", "/health")
        assert health["installing"] is False and health["acestep_models"] is False
        assert call("GET", "/setup/install")[1] is None, "no install has run yet"

        job_id = call("POST", "/setup/install")[1]["job_id"]
        again = call("POST", "/setup/install")[1]["job_id"]
        assert again == job_id, "starting while one runs should join it, not start a second"
        assert call("GET", "/health")[1]["installing"] is True

        job = wait_for(call, job_id, lambda j: j["status"] in ("done", "error"))
        assert job["status"] == "done", job["error"]
        assert [s["id"] for s in job["progress"]["steps"]] == [i for i, _ in installer.STEPS]
        assert set(states(job).values()) == {"done"}, states(job)
        assert any(line.startswith("==> ") for line in job["progress"]["log"])
        assert job["progress"]["finished_at"] and job["progress"]["bytes"] is None
        assert call("GET", "/setup/install")[1]["id"] == job_id
        assert call("GET", "/health")[1]["installing"] is False
        assert call("POST", "/setup/install")[1]["job_id"] != job_id, "a finished install should allow a new one"


def test_simulated_install_can_be_cancelled() -> None:
    with engine(CADENCE_MOCK_INSTALL_DELAY="0.8") as call:
        assert call("POST", "/setup/install/cancel", expect_error=True)[0] == 404, "nothing to cancel yet"
        job_id = call("POST", "/setup/install")[1]["job_id"]
        wait_for(call, job_id, lambda j: j["progress"] and "running" in states(j).values())
        assert call("POST", "/setup/install/cancel")[1] == {"ok": True}

        job = wait_for(call, job_id, lambda j: j["status"] in ("done", "error"))
        assert job["status"] == "error" and job["error"] == "Cancelled", job
        assert job["progress"]["cancelled"] is True
        assert "running" not in states(job).values(), states(job)
        assert states(job)["verify"] == "pending", "it kept working after cancel: " + str(states(job))
        assert call("GET", "/health")[1]["installing"] is False


def test_simulated_install_failure_is_reported() -> None:
    with engine(CADENCE_MOCK_INSTALL_DELAY="0.1", CADENCE_MOCK_INSTALL_FAIL="music") as call:
        job_id = call("POST", "/setup/install")[1]["job_id"]
        job = wait_for(call, job_id, lambda j: j["status"] in ("done", "error"))
        assert job["status"] == "error"
        assert "Simulated failure" in job["error"], job["error"]
        s = states(job)
        assert (s["check"], s["uv"], s["music"], s["voice"]) == ("done", "done", "error", "pending"), s


# ------------------------------------------------------------------- runner


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--network", action="store_true", help="also download the real pinned uv")
    args = ap.parse_args()

    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    if not args.network:
        tests = [t for t in tests if t is not test_real_uv_download]

    failed = 0
    for test in tests:
        name = test.__name__.removeprefix("test_").replace("_", " ")
        try:
            test()
            print(f"PASS  {name}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL  {name}: {exc}")
            if not isinstance(exc, AssertionError):
                traceback.print_exc()
    shutil.rmtree(_SCRATCH, ignore_errors=True)
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
