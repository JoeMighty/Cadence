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
# --add-data's separator is ';' on Windows and ':' everywhere else.
sep=":"
case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*|Windows_NT)
    extra_hidden=(--hidden-import win32ctypes.pywin32 --hidden-import win32timezone)
    sep=";"
    ;;
esac

# The *_helper.py scripts run under the Applio interpreter, not this one, so they
# must ship as real files next to the frozen app package rather than as bytecode.
# --add-data sources resolve relative to --specpath, hence the leading '../'.
uv run pyinstaller --onefile --name cadence-engine \
  --distpath dist_engine --workpath build_engine --specpath build_engine --noconfirm \
  --collect-all uvicorn --collect-all anthropic --collect-all keyring --copy-metadata keyring \
  --add-data "../app/remix_helper.py${sep}app" --add-data "../app/mp3_helper.py${sep}app" \
  --hidden-import app.main ${extra_hidden[@]+"${extra_hidden[@]}"} \
  run_engine.py

triple="$(rustc -vV | sed -n 's/^host: //p')"
ext=""
[ -f "dist_engine/cadence-engine.exe" ] && ext=".exe"
dest="$here/../app/src-tauri/binaries"
mkdir -p "$dest"
cp "dist_engine/cadence-engine$ext" "$dest/cadence-engine-$triple$ext"
echo "sidecar ready: $dest/cadence-engine-$triple$ext"
