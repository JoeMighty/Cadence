# Changelog

All notable changes to Cadence. Installers for every version are on
[GitHub Releases](https://github.com/JoeMighty/Cadence/releases).

## v0.1.8 — 18 Jul 2026

- **Error log** in Settings → Diagnostics: when a generation fails, the details
  (with traceback) are written to a local log you can read, copy into a bug
  report, clear, or open the folder for. Local only, nothing is sent anywhere.
- Groundwork for macOS and Linux: the engine resolves venv paths, the GPU
  probe, and keychain access per platform, and the app shell opens links and
  shuts the engine down portably. No change to how Cadence behaves on Windows.

## v0.1.7 — 17 Jul 2026

- Generate splits into two tabs: **Describe it** (Cadence writes the lyrics) and
  **Your lyrics** (sung exactly as written, with an example template and a style line).
- Generic **Male** / **Female** voices — sing without training a profile (the music model's
  own synthesized singer, not a real person).
- **OpenAI** and **Gemini** join Ollama and Claude as lyric writers; Settings gets a
  provider dropdown with the API key field directly under it.
- First launch opens the setup checklist when something's missing, or shows a one-time
  "you're good to go" when nothing is.
- README rewritten; roadmap simplified.

## v0.1.6 — 16 Jul 2026

- Songs up to **5 minutes**, plus an **Auto** length that sizes the song to the lyrics.
- Fuller lyrics example showing the whole shape (Intro, Pre-Chorus, Bridge, Outro).
- Voice profiles carry a **vocal range** (male/female) so generation starts the vocal in
  the right register before conversion. Existing databases migrate automatically.

## v0.1.5 — 15 Jul 2026

- Everything moves to **`Music\Cadence`**. Windows quietly gives app-spawned processes a
  virtualized, private view of AppData — installed models looked missing and new tracks
  vanished into an overlay. Music is never virtualized.
- **Settings → Storage**: see the exact folder the engine is using, point Cadence at a
  different one, and restart the engine to apply it.
- **Generate → Advanced**: choose where finished tracks are saved, and optionally save the
  separated stems (`.vocals.wav` + `.instrumental.wav`) next to the track.
- In-app setup checklist ("See what's missing") with live status for git, uv, the music
  and voice backends, and Ollama.
- `setup-backends.ps1` installs to `Music\Cadence\vendor`; `-MoveFrom` migrates an
  existing checkout instantly and junctions it back.

## v0.1.4 — 15 Jul 2026

- The app passes the model location to the engine explicitly when it starts it.

## v0.1.3 — 15 Jul 2026

- The "finish setup" banner rechecks the backend every few seconds instead of latching on
  a cold start, and its copy explains the one-time step.

## v0.1.2 — 14 Jul 2026

- Settings → About shows the app version and a **Check for updates** button that compares
  against the latest GitHub release and links the download.

## v0.1.1 — 14 Jul 2026

- Paste your own lyrics (with an example) instead of having them written for you.
- The installed app looks for its models in a stable per-user folder, set up once with
  `scripts/setup-backends.ps1`; clearer errors when they're missing.
- Full-height window layout; the Generate view no longer floats.

## v0.1.0 — 13 Jul 2026

- First Windows installer (`.msi`, unsigned pre-release).
- The full loop: describe a song → lyrics and style from Ollama or Claude → ACE-Step
  generates the track → Demucs isolates the vocal → RVC re-voices it with a voice trained
  in-app → remixed and saved to the Library with WAV/MP3 export.
- The app starts and stops its own engine; API keys live in the OS keychain; dark mode.
