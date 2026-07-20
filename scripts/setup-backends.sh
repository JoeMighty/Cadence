#!/usr/bin/env bash
# setup-backends.sh - one-time install of Cadence's AI backends (macOS/Linux).
#
# The installed Cadence app ships without the ~10 GB music/voice models (they
# can't fit in the bundle). This script clones and builds them into the stable
# per-user folder the app looks in:
#
#     ~/Music/Cadence/vendor/ACE-Step-1.5   (music generation)
#     ~/Music/Cadence/vendor/Applio          (voice conversion + Demucs)
#
# (~/Music/Cadence is where the engine resolves its data root on every OS, so
# the backends installed here are found without extra configuration.)
#
# Run it once:
#
#     bash scripts/setup-backends.sh
#
# Re-running is safe: it checks out the pinned commit and reuses existing
# environments. Pass --vendor-dir to install elsewhere (then set CADENCE_DATA_DIR
# / the per-backend env vars so the engine follows).
#
# Already built the backends in a checkout (engine/vendor)? Skip the multi-GB
# rebuild: --move-from MOVES them into the stable folder and leaves symlinks
# behind so the checkout keeps working:
#
#     bash scripts/setup-backends.sh --move-from ./engine/vendor
#
# Requirements: git and uv on PATH. Linux needs an NVIDIA GPU + recent driver
# for CUDA; macOS runs on Apple Silicon (MPS) or CPU. The first music generation
# (not this script) downloads the model weights.
set -euo pipefail

usage() {
    # Print the header comment block (everything after the shebang, up to the
    # first non-comment line), stripping the leading "# ".
    awk 'NR==1 { next } /^#/ { sub(/^# ?/, ""); print; next } { exit }' "$0"
}

vendor_dir="$HOME/Music/Cadence/vendor"
move_from=""

while [ $# -gt 0 ]; do
    case "$1" in
        --vendor-dir) vendor_dir="$2"; shift 2 ;;
        --move-from)  move_from="$2";  shift 2 ;;
        -h|--help)    usage; exit 0 ;;
        *) echo "unknown option: $1 (try --help)" >&2; exit 2 ;;
    esac
done

# Pinned to the commits Cadence is tested against. Bump together with a release.
ace_repo="https://github.com/ACE-Step/ACE-Step-1.5.git"
ace_commit="6d467e4b5081ccb0abf1ec1bf4fdf9051a2d34b0"
applio_repo="https://github.com/IAHispano/Applio.git"
applio_commit="178c86a4750970659496ec67038f5729dd74092b"

# CUDA 12.8 wheels on Linux (matches the torch build both backends pin); macOS
# has no CUDA, so it takes the default PyPI wheels (Apple Silicon MPS or CPU).
case "$(uname -s)" in
    Darwin*) torch_index="" ;;
    *)       torch_index="https://download.pytorch.org/whl/cu128" ;;
esac

info() { printf '==> %s\n' "$1"; }
ok()   { printf '    %s\n' "$1"; }

need() {
    command -v "$1" >/dev/null 2>&1 || { echo "'$1' was not found on PATH. $2" >&2; exit 1; }
}

# Clone (or update) $1 into $3 and hard-check-out $2.
fetch_repo() {
    local repo="$1" commit="$2" dest="$3"
    if [ -d "$dest/.git" ]; then
        info "Updating $(basename "$dest")"
        git -C "$dest" fetch --depth 1 origin "$commit"
    else
        info "Cloning $(basename "$dest")"
        git clone --filter=blob:none "$repo" "$dest"
        git -C "$dest" fetch --depth 1 origin "$commit"
    fi
    git -C "$dest" checkout --force "$commit"
    ok "at $commit"
}

info "Cadence backends -> $vendor_dir"

# Fast path: MOVE already-built backends out of a checkout into the stable
# folder (instant on the same filesystem), leaving symlinks behind so the
# checkout keeps working.
if [ -n "$move_from" ]; then
    src="$(cd "$move_from" && pwd)"
    mkdir -p "$vendor_dir"
    for name in "ACE-Step-1.5" "Applio"; do
        target="$src/$name"
        dest="$vendor_dir/$name"
        if [ -L "$target" ]; then
            echo "$target is already a symlink - nothing to move. Its target may already be in place." >&2
            exit 1
        fi
        if [ ! -x "$target/.venv/bin/python" ]; then
            echo "No built backend at $target (expected .venv/bin/python). Build it there first, or drop --move-from to install fresh." >&2
            exit 1
        fi
        rm -rf "$dest"
        info "Moving $name -> $dest"
        mv "$target" "$dest"
        ln -s "$dest" "$target"
        ok "$name moved; checkout symlinked back"
    done
    echo
    info "Done. The backends live in $vendor_dir; the checkout still sees them."
    exit 0
fi

need git "Install Git from your package manager (e.g. 'brew install git' or 'apt install git')."
need uv  "Install uv from https://docs.astral.sh/uv/getting-started/installation/"
mkdir -p "$vendor_dir"

# --- ACE-Step (music generation) -------------------------------------------
ace_dir="$vendor_dir/ACE-Step-1.5"
fetch_repo "$ace_repo" "$ace_commit" "$ace_dir"
info "Building ACE-Step environment (uv sync) - this pulls PyTorch, a few GB"
( cd "$ace_dir" && uv sync )
ok "ACE-Step ready"

# --- Applio (voice conversion) + Demucs (vocal separation) ------------------
applio_dir="$vendor_dir/Applio"
fetch_repo "$applio_repo" "$applio_commit" "$applio_dir"
applio_py="$applio_dir/.venv/bin/python"
if [ ! -x "$applio_py" ]; then
    info "Creating Applio environment (Python 3.12)"
    ( cd "$applio_dir" && uv venv --python 3.12 .venv )
fi
info "Installing Applio dependencies - this pulls PyTorch, a few GB"
if [ -n "$torch_index" ]; then
    ( cd "$applio_dir" && uv pip install --python "$applio_py" -r requirements.txt \
        --extra-index-url "$torch_index" --index-strategy unsafe-best-match )
else
    ( cd "$applio_dir" && uv pip install --python "$applio_py" -r requirements.txt )
fi
info "Installing Demucs (vocal separation) into the Applio environment"
( cd "$applio_dir" && uv pip install --python "$applio_py" demucs )
ok "Applio + Demucs ready"

echo
info "Done. Cadence will find the backends at $vendor_dir"
ok "Open Cadence and generate - the first run downloads the model weights (~10 GB)."
