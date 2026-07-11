"""Phase 1 verification: drive the engine's generate and convert-voice
endpoints end to end and confirm real audio comes back.

Usage:
    python scripts/verify_phase1.py [--engine URL] [--pth PATH --index PATH --input WAV]

Without --pth/--index, the voice step uses whatever the engine's mock mode
provides (CADENCE_MOCK=1); with them, it exercises real RVC conversion.
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
import time
import urllib.request


def call(method: str, url: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


def wait_for_job(engine: str, job_id: str, timeout: float = 2400) -> dict:
    start = time.time()
    last_detail = ""
    while time.time() - start < timeout:
        job = call("GET", f"{engine}/status/{job_id}")
        if job["detail"] != last_detail:
            print(f"  [{job['status']}] {job['detail']}")
            last_detail = job["detail"]
        if job["status"] in ("done", "error"):
            return job
        time.sleep(5)
    raise TimeoutError(f"job {job_id} did not finish in {timeout}s")


def check_wav(path: str) -> str:
    with open(path, "rb") as fh:
        header = fh.read(64)
    if header[:4] != b"RIFF" or header[8:12] != b"WAVE":
        raise ValueError(f"{path} is not a WAV file")
    fmt = struct.unpack("<H", header[20:22])[0]
    ch = struct.unpack("<H", header[22:24])[0]
    sr = struct.unpack("<I", header[24:28])[0]
    return f"wav ok: format={fmt} channels={ch} rate={sr}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", default="http://127.0.0.1:8000")
    ap.add_argument("--pth", default="")
    ap.add_argument("--index", default="")
    ap.add_argument("--input", default="", help="input WAV for voice conversion")
    args = ap.parse_args()

    print("1. /health")
    health = call("GET", f"{args.engine}/health")
    print(f"   {health}")

    print("2. /generate")
    gen = call("POST", f"{args.engine}/generate", {
        "prompt": "warm acoustic guitar instrumental, slow tempo, late night feel",
        "instrumental": True,
        "duration": 15,
    })
    job = wait_for_job(args.engine, gen["job_id"])
    if job["status"] != "done":
        print(f"FAIL: generation errored: {job['error']}")
        return 1
    music_path = job["result"]["audio_path"]
    print(f"   {check_wav(music_path)}")
    print(f"   metas: {job['result'].get('metas')}")

    print("3. /convert-voice")
    payload: dict = {"input_path": args.input or music_path}
    if args.pth:
        payload.update({"pth_path": args.pth, "index_path": args.index})
    conv = call("POST", f"{args.engine}/convert-voice", payload)
    job = wait_for_job(args.engine, conv["job_id"])
    if job["status"] != "done":
        print(f"FAIL: conversion errored: {job['error']}")
        return 1
    print(f"   {check_wav(job['result']['audio_path'])}")

    print("PASS: generate and convert-voice both produced audio")
    return 0


if __name__ == "__main__":
    sys.exit(main())
