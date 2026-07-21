# Changelog

All notable changes to Cadence. Installers for every version are on
[GitHub Releases](https://github.com/JoeMighty/Cadence/releases).

## Unreleased

- **Autotune and smoothing, for songs sung in your own voice.** Both live under
  Advanced on the Generate screen. Autotune (off, subtle, strong) pulls the singing
  towards the nearest note. Smoothing (off, light, strong) protects breath and
  voiceless consonants and cleans up the noise the conversion leaves behind, which
  is usually what makes a cloned vocal sound raspy. They are greyed out for
  instrumentals and generic voices, where there is no conversion to shape.

## v0.2.0 — 21 Jul 2026

- **Every song now gets its own dated folder.** A new track lands in something like
  `output/2026-07-21_15-32-01/` with `track.wav` inside, next to the pre-conversion
  `music.wav`, the isolated `vocal.wav`, and any stems you asked to keep. The folders
  sort in the order you made them. Tracks you already have stay exactly where they
  are and keep playing.
- **macOS and Linux join Windows.** Every release now ships a `.dmg` (macOS), a
  `.deb` (Linux), and the `.msi` (Windows), each built and smoke-tested on its own
  operating system in CI. **macOS and Linux are under testing** — the app and its
  engine run, but real music generation isn't verified there yet: the models want an
  NVIDIA GPU (so Linux needs CUDA), and Apple Silicon support is unconfirmed. Windows
  stays the fully tested path.
- **`setup-backends.sh`** installs the AI backends on macOS and Linux, mirroring the
  Windows PowerShell setup script.
- Continuous integration builds all three platforms and drafts a release on each
  version tag.
- **Voices can be renamed, and deleting one now really deletes it.** Click Rename to
  edit the name in place. Delete asks before it acts, then clears the recordings and
  the trained model along with the entry and tells you how much space came back.
  Previously it removed only the database entry, so a deleted voice quietly kept its
  recordings and its multi-gigabyte training folder forever.
- **The voice training script is now 75 lines, up from 12.** Reaching the ten
  minutes of speech that unlocks training used to mean reading the same dozen
  lines five times over, which is dull and teaches the model your bored voice.
  The new lines cover statements, questions, counting, clipped fragments and
  long sentences, so one pass through is enough.
- The installer wears Cadence's own artwork now, and the app icon's mark is
  centred by its visual weight rather than its bounding box, so it no longer
  looks nudged to the right in the taskbar and Start menu.
- **Fixed:** in the installed app, making a song in your own voice failed with a
  "no such file or directory" error, and MP3 export failed the same way. The two
  helper scripts that run inside the Applio environment were missing from the
  packaged engine, so they only worked when running from source.

## v0.1.10 — 19 Jul 2026

- **A player that follows you**: playing a track opens a bar along the bottom that
  keeps going as you move between Generate, Library, and Settings. Play/pause, skip
  through the library as a queue, scrub the timeline, or close it.
- **A Library worth returning to**: search across prompts, lyrics, and voice names;
  **favorite** the ones you want to keep and filter down to just those; and **Remix**
  any track to drop its prompt, lyrics, and voice back into Generate as a starting
  point. Favorites are stored with the track, so they survive restarts.

## v0.1.9 — 18 Jul 2026

- **Regenerate a section**: on a finished instrumental track, open "Regenerate a
  part", pick a time range, and the model regenerates just that stretch (with an
  optional new direction) while keeping the rest — a new track, the original
  untouched. Uses ACE-Step's native repaint. Voice-track sections need per-part
  conversion and are still to come.

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
