<div align="center">

<img src="app/src-tauri/icons/128x128.png" width="96" alt="Cadence" />

# Cadence

**Full songs from a sentence, sung in your own voice.**

A local-first desktop AI music generator. Cadence writes, composes, and performs complete
tracks from a text prompt in any language, and always sings in a voice cloned from a few
minutes of your own speech — on your GPU, with no per-song cost.

![Platform](https://img.shields.io/badge/platform-Windows-5856D6?style=plastic)
![Tauri](https://img.shields.io/badge/Tauri-2-24C8DB?style=plastic&logo=tauri&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-16-000000?style=plastic&logo=nextdotjs&logoColor=white)
![FastAPI](https://img.shields.io/badge/engine-FastAPI-009688?style=plastic&logo=fastapi&logoColor=white)
![CUDA](https://img.shields.io/badge/GPU-CUDA-76B900?style=plastic&logo=nvidia&logoColor=white)
![Release](https://img.shields.io/github/v/release/JoeMighty/Cadence?style=plastic&color=5856D6)

[Website](https://joemighty.github.io/Cadence/) · [Roadmap](https://joemighty.github.io/Cadence/roadmap.html) · [Setup](https://joemighty.github.io/Cadence/setup.html) · [Support](https://joemighty.github.io/Cadence/support.html)

</div>

## What it does

- **Describe it, or paste your own lyrics** — two tabs on Generate: a plain-language prompt
  (Cadence writes the lyrics), or your own lyrics sung exactly as written, shaped with
  `[Verse]` / `[Chorus]` / `[Bridge]` tags.
- **A voice that never drifts** — train once from a short reading session; every track sings in
  that same voice. Profiles carry a vocal range (male/female) so generation starts in the right
  register — or skip training and pick a generic **Male** / **Female** voice, or **Instrumental**.
- **Songs up to 5 minutes** — or set Length to *Auto* and the song sizes itself to the lyrics.
- **Your files, your folders** — tracks land in `Music\Cadence` (or any folder you choose per
  generation), with optional separated stems (`.vocals.wav` + `.instrumental.wav`), and WAV/MP3
  export from the Library.
- **Any language, any provider** — lyrics come from Ollama (local, free), Claude, OpenAI, or
  Gemini; keys live in the OS keychain.
- **Local by default** — generation runs on your own GPU. No subscription, no upload, no
  per-song cost. A native Tauri app, not a browser tab.

Four screens: **Generate**, **Voice** (record and train), **Library**, and **Settings**
(provider + keys, storage location, GPU status, update check). First launch shows a live
setup checklist if anything's missing — and a "good to go" when nothing is.

## How it works

```
prompt or lyrics ─▶ text provider ─▶ ACE-Step ─▶ Demucs ─▶ RVC (your voice) ─▶ remix ─▶ track
                    (Ollama/Claude/    (music)    (split)   (re-voice vocal)    (recombine)
                     OpenAI/Gemini)
```

The text provider turns a prompt into a style caption and structured lyrics (skipped when you
bring your own). ACE-Step generates the track; Demucs isolates the vocal so RVC re-voices only
the vocal (not the full mix); the converted vocal is remixed over the original instrumental.

## Install (Windows)

1. Download the `.msi` from the [latest release](https://github.com/JoeMighty/Cadence/releases)
   (unsigned for now — SmartScreen: *More info → Run anyway*).
2. Install the AI backends once (needs `git` and `uv` on PATH):

   ```
   git clone https://github.com/JoeMighty/Cadence.git
   powershell -ExecutionPolicy Bypass -File Cadence\scripts\setup-backends.ps1
   ```

   They land in `Music\Cadence\vendor`, where the app looks. The in-app checklist
   (*See what's missing*) tracks the same steps.
3. Open Cadence, wait for the green **Engine online** dot, and generate. The first song
   downloads the model weights (~10 GB).

## Architecture

- `app/` — Tauri 2 desktop shell (Rust) with a Next.js (static export) frontend. On launch the
  shell starts the engine as a bundled sidecar and stops it on exit.
- `engine/` — local Python (FastAPI) engine that orchestrates generation, voice training, and
  conversion, called over `localhost`. It drives ACE-Step and Applio (RVC) in their own
  environments under `Music\Cadence\vendor` (installed apps) or `engine/vendor/` (dev checkouts;
  `setup-backends.ps1 -MoveFrom` keeps both working via junctions).

## Running from source

**Engine** — creates its environment on first run:

```
cd engine
uv sync
uv run uvicorn app.main:app --port 8000
```

**App** — in a second terminal:

```
cd app
npm install
npm run tauri dev
```

Full music generation additionally needs the vendor backends (ACE-Step, Applio + Demucs) set up
under `engine/vendor/`, and optionally [Ollama](https://ollama.com) for local lyrics. See the
[setup guide](https://joemighty.github.io/Cadence/setup.html).

## Building the Windows installer

```
bash scripts/build-sidecar.sh   # package the engine into a sidecar exe (PyInstaller)
cd app && npm run tauri build   # build the app and bundle the .msi
```

Produces `Cadence_<version>_x64_en-US.msi` under `app/src-tauri/target/release/bundle/msi/`,
bundling the engine sidecar so the installed app starts and stops the engine on its own.
(Currently unsigned — Windows SmartScreen will warn until code signing is added.)

## Status

Windows first; macOS and Linux later. The full loop shipped — see the
[roadmap](https://joemighty.github.io/Cadence/roadmap.html) for what's next and the
[changelog](CHANGELOG.md) for version-by-version detail.

## Credit

Built by Jobin Bennykutty — [github.com/JoeMighty](https://github.com/JoeMighty/)
