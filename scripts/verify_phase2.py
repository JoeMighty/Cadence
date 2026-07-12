"""Phase 2 verification: drive the voice endpoints end to end.

Creates a profile, uploads a folder of WAV takes, starts training, polls
the profile to `ready`, and confirms the model and index exist on disk.

Usage:
    python scripts/verify_phase2.py --takes <dir> [--engine URL] [--epochs N]

Point --takes at a folder of WAV files. In real mode the engine enforces
a minimum-audio threshold; set CADENCE_VOICE_UNLOCK_SECONDS low on the
engine when testing with short clips.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path


def call(method: str, url: str, payload: dict | None = None, raw: bytes | None = None) -> dict:
    if raw is not None:
        data, ctype = raw, "audio/wav"
    elif payload is not None:
        data, ctype = json.dumps(payload).encode(), "application/json"
    else:
        data, ctype = None, None
    req = urllib.request.Request(url, data=data, method=method)
    if ctype:
        req.add_header("Content-Type", ctype)
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", default="http://127.0.0.1:8000")
    ap.add_argument("--takes", required=True, help="folder of WAV takes")
    ap.add_argument("--epochs", type=int, default=3)
    args = ap.parse_args()

    wavs = sorted(Path(args.takes).glob("*.wav"))
    if not wavs:
        print(f"FAIL: no WAV files in {args.takes}")
        return 1

    print("1. create profile")
    profile = call("POST", f"{args.engine}/voice/profiles", {"name": "Verify Voice"})
    pid = profile["id"]
    print(f"   id={pid}")

    print(f"2. upload {len(wavs)} takes")
    total = 0.0
    for i, wav in enumerate(wavs):
        res = call("POST", f"{args.engine}/voice/profiles/{pid}/takes?script_index={i}",
                   raw=wav.read_bytes())
        total = res["profile"]["total_seconds"]
        print(f"   {wav.name}: +{res['take']['seconds']:.1f}s  total={total:.1f}s")

    print(f"3. train ({args.epochs} epochs)")
    call("POST", f"{args.engine}/voice/profiles/{pid}/train", {"epochs": args.epochs})

    last = ""
    start = time.time()
    while time.time() - start < 3600:
        p = call("GET", f"{args.engine}/voice/profiles/{pid}")
        if p["detail"] != last:
            print(f"   [{p['status']}] {p['detail']}")
            last = p["detail"]
        if p["status"] == "ready":
            model, index = Path(p["model_path"]), Path(p["index_path"])
            ok = model.exists() and index.exists()
            print(f"   model: {model.name} ({'exists' if model.exists() else 'MISSING'})")
            print(f"   index: {index.name} ({'exists' if index.exists() else 'MISSING'})")
            print("PASS: voice trained and registered" if ok else "FAIL: model/index missing")
            return 0 if ok else 1
        if p["status"] == "error":
            print(f"FAIL: training errored: {p['error']}")
            return 1
        time.sleep(5)
    print("FAIL: timed out")
    return 1


if __name__ == "__main__":
    sys.exit(main())
