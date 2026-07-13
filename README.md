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

- **A voice that never drifts** — train once from a short reading session; every track sings in that same voice.
- **Any language** — prompt in one language, sing in another; lyrics and style come from a language model.
- **Local by default** — generation runs on your own GPU. No subscription, no upload. Cloud providers are optional.
- **A native desktop app** — Tauri, not a browser tab.

Four screens: **Generate** (prompt → song), **Voice** (record and train), **Library** (play, delete, export WAV/MP3), and **Settings** (provider toggle, API keys in the OS keychain, GPU status).

## How it works

```
prompt ─▶ text provider ─▶ ACE-Step ─▶ Demucs ─▶ RVC (your voice) ─▶ remix ─▶ track
         (Ollama/Claude)   (music)    (split)   (re-voice vocal)   (recombine)
```

The text provider turns a prompt into a style caption and structured lyrics. ACE-Step generates
the track; Demucs isolates the vocal so RVC re-voices only the vocal (not the full mix); the
converted vocal is remixed over the original instrumental.

## Architecture

- `app/` — Tauri 2 desktop shell (Rust) with a Next.js (static export) frontend. On launch the
  shell starts the engine as a bundled sidecar and stops it on exit.
- `engine/` — local Python (FastAPI) engine that orchestrates generation, voice training, and
  conversion, called over `localhost`. It drives ACE-Step and Applio (RVC) in their own
  environments under `engine/vendor/`.

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

Windows first; macOS and Linux later. Phases 0–7 shipped — see the
[roadmap](https://joemighty.github.io/Cadence/roadmap.html).

## Credit

Built by Jobin Bennykutty — [github.com/JoeMighty](https://github.com/JoeMighty/)
