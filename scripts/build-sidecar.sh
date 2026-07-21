#!/usr/bin/env bash
# Build the engine into a standalone sidecar binary and place it where the Tauri
# bundler expects it (binaries/cadence-engine-<target-triple>[.exe]). Run this
# before `npm run tauri build`. Works on Windows, macOS, and Linux.
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
cd "$here/../engine"

# Windows needs the pywin32 helpers keyring uses for the Credential Manager;
# macOS/Linux use their own keyring backends and must not import pywin32.
extra_hidden=()
case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*|Windows_NT)
    extra_hidden=(--hidden-import win32ctypes.pywin32 --hidden-import win32timezone)
    ;;
esac

uv run pyinstaller --onefile --name cadence-engine \
  --distpath dist_engine --workpath build_engine --specpath build_engine --noconfirm \
  --collect-all uvicorn --collect-all anthropic --collect-all keyring --copy-metadata keyring \
  --hidden-import app.main ${extra_hidden[@]+"${extra_hidden[@]}"} \
  run_engine.py

triple="$(rustc -vV | sed -n 's/^host: //p')"
ext=""
[ -f "dist_engine/cadence-engine.exe" ] && ext=".exe"
dest="$here/../app/src-tauri/binaries"
mkdir -p "$dest"
cp "dist_engine/cadence-engine$ext" "$dest/cadence-engine-$triple$ext"
echo "sidecar ready: $dest/cadence-engine-$triple$ext"
