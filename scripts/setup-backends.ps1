<#
    setup-backends.ps1 - one-time install of Cadence's AI backends.

    The installed Cadence app ships without the ~10 GB music/voice models (they
    can't fit in an .msi). This script clones and builds them into the stable
    per-user folder the app looks in:

        %USERPROFILE%\Music\Cadence\vendor\ACE-Step-1.5   (music generation)
        %USERPROFILE%\Music\Cadence\vendor\Applio          (voice conversion + Demucs)

    (Music, not AppData: Windows can give the app a virtualized private view of
    AppData, where installed files look missing. Music is never virtualized.)

    Run it once from a normal PowerShell window:

        powershell -ExecutionPolicy Bypass -File scripts\setup-backends.ps1

    Re-running is safe: it checks out the pinned commit and reuses existing
    environments. Pass -VendorDir to install somewhere else (then set
    CADENCE_DATA_DIR / the per-backend env vars so the engine follows).

    Already have the backends built in a repo checkout (engine/vendor)? Skip the
    multi-GB rebuild: -MoveFrom MOVES them into the stable folder (instant on the
    same drive) and leaves junctions behind so the checkout keeps working:

        powershell -ExecutionPolicy Bypass -File scripts\setup-backends.ps1 -MoveFrom .\engine\vendor

    Requirements: git and uv on PATH, and an NVIDIA GPU with a recent driver.
    The first music generation (not this script) downloads the model weights.
#>

[CmdletBinding()]
param(
    [string]$VendorDir = (Join-Path ([Environment]::GetFolderPath("MyMusic")) "Cadence\vendor"),
    [string]$MoveFrom
)

$ErrorActionPreference = "Stop"

# Pinned to the commits Cadence is tested against. Bump together with a release.
$AceRepo   = "https://github.com/ACE-Step/ACE-Step-1.5.git"
$AceCommit = "6d467e4b5081ccb0abf1ec1bf4fdf9051a2d34b0"
$ApplioRepo   = "https://github.com/IAHispano/Applio.git"
$ApplioCommit = "178c86a4750970659496ec67038f5729dd74092b"

# CUDA 12.8 wheels - matches the torch build both backends pin.
$TorchIndex = "https://download.pytorch.org/whl/cu128"

function Info($msg)  { Write-Host "==> $msg" -ForegroundColor Cyan }
function Ok($msg)    { Write-Host "    $msg" -ForegroundColor Green }

function Need($exe, $hint) {
    if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) {
        throw "'$exe' was not found on PATH. $hint"
    }
}

# Run an external command and fail the script if it returns non-zero.
function Run($file, [string[]]$arguments, $workdir) {
    Push-Location $workdir
    try {
        & $file @arguments
        if ($LASTEXITCODE -ne 0) {
            throw "$file $($arguments -join ' ') failed with exit code $LASTEXITCODE"
        }
    } finally {
        Pop-Location
    }
}

# Clone (or update) $repo into $dest and hard-check-out $commit.
function Fetch-Repo($repo, $commit, $dest) {
    if (Test-Path (Join-Path $dest ".git")) {
        Info "Updating $(Split-Path $dest -Leaf)"
        Run "git" @("fetch", "--depth", "1", "origin", $commit) $dest
    } else {
        Info "Cloning $(Split-Path $dest -Leaf)"
        Run "git" @("clone", "--filter=blob:none", $repo, $dest) (Split-Path $dest -Parent)
        Run "git" @("fetch", "--depth", "1", "origin", $commit) $dest
    }
    Run "git" @("checkout", "--force", $commit) $dest
    Ok "at $commit"
}

Info "Cadence backends -> $VendorDir"

# Fast path: MOVE already-built backends out of a checkout into the stable
# folder (instant on the same drive), leaving junctions behind so the checkout
# keeps working. Real directories, not links — the app must never depend on
# reparse points it may not be allowed to follow.
if ($MoveFrom) {
    $src = (Resolve-Path $MoveFrom).Path
    New-Item -ItemType Directory -Force -Path $VendorDir | Out-Null
    foreach ($name in @("ACE-Step-1.5", "Applio")) {
        $target = Join-Path $src $name
        $dest = Join-Path $VendorDir $name
        $item = Get-Item $target -ErrorAction SilentlyContinue
        if ($item -and $item.LinkType) {
            throw "$target is already a link ($($item.LinkType)) - nothing to move. Its target may already be in place."
        }
        $venv = Join-Path $target ".venv\Scripts\python.exe"
        if (-not (Test-Path $venv)) {
            throw "No built backend at $target (expected $venv). Build it there first, or drop -MoveFrom to install fresh."
        }
        if (Test-Path $dest) { Remove-Item $dest -Force -Recurse }
        Info "Moving $name -> $dest"
        Move-Item -Path $target -Destination $dest
        New-Item -ItemType Junction -Path $target -Target $dest | Out-Null
        Ok "$name moved; checkout junctioned back"
    }
    Write-Host ""
    Info "Done. The backends live in $VendorDir; the checkout still sees them."
    return
}

Need "git" "Install Git from https://git-scm.com/download/win"
Need "uv"  "Install uv from https://docs.astral.sh/uv/getting-started/installation/"
New-Item -ItemType Directory -Force -Path $VendorDir | Out-Null

# --- ACE-Step (music generation) -------------------------------------------
$AceDir = Join-Path $VendorDir "ACE-Step-1.5"
Fetch-Repo $AceRepo $AceCommit $AceDir
Info "Building ACE-Step environment (uv sync) - this pulls PyTorch, a few GB"
Run "uv" @("sync") $AceDir
Ok "ACE-Step ready"

# --- Applio (voice conversion) + Demucs (vocal separation) ------------------
$ApplioDir = Join-Path $VendorDir "Applio"
Fetch-Repo $ApplioRepo $ApplioCommit $ApplioDir
$ApplioPy = Join-Path $ApplioDir ".venv\Scripts\python.exe"
if (-not (Test-Path $ApplioPy)) {
    Info "Creating Applio environment (Python 3.12)"
    Run "uv" @("venv", "--python", "3.12", ".venv") $ApplioDir
}
Info "Installing Applio dependencies - this pulls PyTorch, a few GB"
Run "uv" @(
    "pip", "install", "--python", $ApplioPy,
    "-r", "requirements.txt",
    "--extra-index-url", $TorchIndex,
    "--index-strategy", "unsafe-best-match"
) $ApplioDir
Info "Installing Demucs (vocal separation) into the Applio environment"
Run "uv" @("pip", "install", "--python", $ApplioPy, "demucs") $ApplioDir
Ok "Applio + Demucs ready"

Write-Host ""
Info "Done. Cadence will find the backends at $VendorDir"
Write-Host "    Open Cadence and generate - the first run downloads the model weights (~10 GB)." -ForegroundColor Green
