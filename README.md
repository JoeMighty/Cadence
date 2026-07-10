# Cadence

A local-first desktop AI music generator. Cadence creates full tracks, instrumental and vocal, from a text prompt in any language, and always sings in your own voice, cloned once from a short recording.

- Persistent voice identity across every track
- Multilingual prompts and lyrics
- Local generation by default, no per-song cost
- Native desktop app (Tauri), not a browser tab

Status: early scaffolding. Windows first, then macOS and Linux.

## Architecture

- `app/` — Tauri 2 desktop shell (Rust) with a Next.js (static export) frontend
- `engine/` — local Python (FastAPI) engine that wraps music generation and voice conversion, called over `localhost`

## Development

**Frontend + shell:**

```
cd app
npm install
npm run tauri dev
```

**Engine:**

```
cd engine
uv sync
uv run uvicorn app.main:app --port 8000
```

The app checks `GET /ping` on the engine at startup.

## Credit

Built by Jobin Bennykutty — [github.com/JoeMighty](https://github.com/JoeMighty/)
