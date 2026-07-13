#!/usr/bin/env bash
# Build the engine into a standalone sidecar exe and place it where the Tauri
# bundler expects it. Run this before `npm run tauri build`.
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
cd "$here/../engine"

uv run pyinstaller --onefile --name cadence-engine \
  --distpath dist_engine --workpath build_engine --specpath build_engine --noconfirm \
  --collect-all uvicorn --collect-all anthropic --collect-all keyring --copy-metadata keyring \
  --hidden-import app.main --hidden-import win32ctypes.pywin32 --hidden-import win32timezone \
  run_engine.py

triple="$(rustc -vV | sed -n 's/^host: //p')"
dest="$here/../app/src-tauri/binaries"
mkdir -p "$dest"
cp dist_engine/cadence-engine.exe "$dest/cadence-engine-$triple.exe"
echo "sidecar ready: $dest/cadence-engine-$triple.exe"
