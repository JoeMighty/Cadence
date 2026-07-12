"""Phase 3 verification: drive /compose end to end.

Structures a prompt into lyrics/style (text provider), generates music,
converts to a trained voice when one is available, and confirms the track
persists with downloadable audio.

Usage:
    python scripts/verify_phase3.py [--engine URL] [--voice ID] [--prompt TEXT]

With no --voice, uses the first `ready` profile if one exists, otherwise
composes an instrumental (which skips the voice step).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request


def call(method: str, url: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"} if data else {})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", default="http://127.0.0.1:8000")
    ap.add_argument("--voice", default="")
    ap.add_argument("--prompt", default="a gentle indie folk song about coming home after a long time away")
    args = ap.parse_args()

    voice_id = args.voice
    if not voice_id:
        ready = [p for p in call("GET", f"{args.engine}/voice/profiles") if p["status"] == "ready"]
        voice_id = ready[0]["id"] if ready else ""
    instrumental = not voice_id
    print(f"voice: {voice_id or '(none, instrumental)'}")

    body = {"prompt": args.prompt, "duration": 15, "instrumental": instrumental}
    if voice_id:
        body["voice_profile_id"] = voice_id

    print("1. /compose")
    job_id = call("POST", f"{args.engine}/compose", body)["job_id"]

    last = ""
    start = time.time()
    while time.time() - start < 2400:
        job = call("GET", f"{args.engine}/status/{job_id}")
        if job["detail"] != last:
            print(f"   [{job['status']}] {job['detail']}")
            last = job["detail"]
        if job["status"] == "done":
            track = job["result"]["track"]
            print(f"   caption: {track['caption'][:80]}")
            print(f"   language: {track['vocal_language']}  bpm: {track['bpm']}  voice: {track['voice_name']}")
            print(f"   lyrics: {(track['lyrics'] or '(instrumental)')[:70].replace(chr(10), ' / ')}")
            # confirm the audio is downloadable
            audio = urllib.request.urlopen(f"{args.engine}/tracks/{track['id']}/audio", timeout=60).read()
            ok = audio[:4] == b"RIFF" and len(audio) > 1000
            print(f"   audio: {len(audio)} bytes ({'WAV ok' if ok else 'BAD'})")
            print("PASS: composed a track end to end" if ok else "FAIL: bad audio")
            return 0 if ok else 1
        if job["status"] == "error":
            print(f"FAIL: {job['error']}")
            return 1
        time.sleep(4)
    print("FAIL: timed out")
    return 1


if __name__ == "__main__":
    sys.exit(main())
