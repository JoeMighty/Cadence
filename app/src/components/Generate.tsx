"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  compose,
  getHealth,
  getJob,
  listProfiles,
  repaintTrack,
  trackAudioUrl,
  type Job,
  type Track,
  type VoiceProfile,
} from "@/lib/engine";
import SetupGuide from "@/components/SetupGuide";

const STEPS_VOICE = ["Writing lyrics", "Generating music", "Converting to your voice"];
const STEPS_INSTRUMENTAL = ["Writing lyrics", "Generating music"];

// Shown when the user opens "Insert example". Section tags drive the song
// structure; the model reads these, not chord names. This one shows the full
// shape — with Length on Auto, more sections mean a longer song.
const EXAMPLE_LYRICS = `[Intro]

[Verse]
City lights are bleeding through the rain
Every window holds another name
Footsteps echo down an empty street
Chasing something I can't quite complete

[Pre-Chorus]
And I keep on running, running
Like the night could set me free

[Chorus]
Hold the line, we're running out of time
Neon signs are painting us in gold
Hold the line, the city's yours and mine
A quiet song before the night grows cold

[Verse]
Coffee going cold on the windowsill
Morning feels a thousand miles uphill
Every promise that we never kept
Sings me back to sleep inside my head

[Pre-Chorus]
And I keep on running, running
Like the night could set me free

[Chorus]
Hold the line, we're running out of time
Neon signs are painting us in gold
Hold the line, the city's yours and mine
A quiet song before the night grows cold

[Bridge]
When the sun comes up we'll be alright
Trading all these shadows for the light

[Chorus]
Hold the line, we're running out of time
Neon signs are painting us in gold
Hold the line, the city's yours and mine
A quiet song before the night grows cold

[Outro]`;

function stepIndex(detail: string): number {
  if (detail.startsWith("Writing")) return 0;
  if (/^(Converting|Separating|Remixing)/.test(detail)) return 2;
  if (
    detail.toLowerCase().includes("music") ||
    detail.startsWith("Starting") ||
    detail.startsWith("Regenerating")
  )
    return 1;
  return 0;
}

export default function Generate({ goToVoice }: { goToVoice: () => void }) {
  const [profiles, setProfiles] = useState<VoiceProfile[]>([]);
  const [mode, setMode] = useState<"prompt" | "lyrics">("prompt");
  const [prompt, setPrompt] = useState("");
  const [styleText, setStyleText] = useState("");
  const [voiceId, setVoiceId] = useState<string>("instrumental");
  const [advanced, setAdvanced] = useState(false);
  const [duration, setDuration] = useState<number | "auto">(30);
  const [lyrics, setLyrics] = useState("");
  const [outputDir, setOutputDir] = useState("");
  const [saveStems, setSaveStems] = useState(false);
  const [backendReady, setBackendReady] = useState(true);
  const [guideOpen, setGuideOpen] = useState(false);
  const [welcome, setWelcome] = useState(false);
  const [repainting, setRepainting] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const ready = profiles.filter((p) => p.status === "ready");
  const instrumental = voiceId === "instrumental";
  const genericVoice = voiceId === "male" || voiceId === "female";
  const track: Track | null = job?.status === "done" ? job.result?.track ?? null : null;
  const running = jobId != null && job?.status !== "done" && job?.status !== "error";
  const canGenerate =
    mode === "prompt" ? !!prompt.trim() : !!lyrics.trim() && !!styleText.trim();

  // Lyrics always need a singer: leaving Instrumental picks a sensible voice.
  function switchMode(next: "prompt" | "lyrics") {
    setMode(next);
    if (next === "lyrics" && voiceId === "instrumental") {
      setVoiceId(ready[0]?.id ?? "female");
    }
  }

  const load = useCallback(async () => {
    try {
      const list = await listProfiles();
      setProfiles(list);
      const firstReady = list.find((p) => p.status === "ready");
      if (firstReady) setVoiceId((v) => (v === "instrumental" ? firstReady.id : v));
    } catch {
      /* engine offline; the shell surfaces this */
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // Output preferences stick across sessions (kept on this machine only).
  useEffect(() => {
    try {
      setOutputDir(localStorage.getItem("cadence-output-dir") ?? "");
      setSaveStems(localStorage.getItem("cadence-save-stems") === "1");
    } catch {}
  }, []);
  useEffect(() => {
    try {
      localStorage.setItem("cadence-output-dir", outputDir);
      localStorage.setItem("cadence-save-stems", saveStems ? "1" : "0");
    } catch {}
  }, [outputDir, saveStems]);

  // Keep the setup banner honest: poll /health rather than checking once. A
  // freshly started engine can miss the model folder on a cold filesystem read,
  // so only surface the banner after two straight misses, and clear it the
  // moment the backend reports in.
  const missesRef = useRef(0);
  useEffect(() => {
    let alive = true;
    const check = async () => {
      try {
        const health = await getHealth();
        if (!alive) return;
        if (health.mock || health.acestep_installed) {
          missesRef.current = 0;
          setBackendReady(true);
          // First run with everything in place: say so once, then stay quiet.
          try {
            if (!localStorage.getItem("cadence-welcomed")) {
              setWelcome(true);
              localStorage.setItem("cadence-welcomed", "1");
            }
          } catch {}
        } else if (++missesRef.current >= 2) {
          setBackendReady(false);
          // Fresh install with missing pieces: open the guide once per launch.
          try {
            if (!sessionStorage.getItem("cadence-guide-shown")) {
              setGuideOpen(true);
              sessionStorage.setItem("cadence-guide-shown", "1");
            }
          } catch {}
        }
      } catch {
        /* engine offline; the shell surfaces that separately */
      }
    };
    check();
    const id = setInterval(check, 4000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  // Poll the compose job while it runs.
  useEffect(() => {
    if (!jobId) return;
    let alive = true;
    const tick = async () => {
      try {
        const j = await getJob(jobId);
        if (!alive) return;
        setJob(j);
        if (j.status === "done" || j.status === "error") return;
      } catch {
        /* transient */
      }
      if (alive) timer = setTimeout(tick, 1500);
    };
    let timer = setTimeout(tick, 500);
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [jobId]);

  async function onGenerate() {
    if (!canGenerate) return;
    setBusy(true);
    setError(null);
    setJob(null);
    setRepainting(false);
    try {
      const res = await compose({
        prompt: (mode === "lyrics" ? styleText : prompt).trim(),
        instrumental,
        voice_profile_id: instrumental || genericVoice ? undefined : voiceId,
        vocal_gender: genericVoice ? (voiceId as "male" | "female") : undefined,
        duration: duration === "auto" ? undefined : duration,
        lyrics: mode === "lyrics" && !instrumental ? lyrics.trim() : undefined,
        output_dir: outputDir.trim() || undefined,
        save_stems: saveStems || undefined,
      });
      setJobId(res.job_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not start generation");
    } finally {
      setBusy(false);
    }
  }

  // Regenerate a time range of the finished track; the result flows through the
  // same job poll and replaces the shown track when it lands.
  async function startRepaint(trackId: string, start: number, end: number, part: string) {
    setError(null);
    setJob(null);
    setRepainting(true);
    try {
      const res = await repaintTrack(trackId, start, end, part);
      setJobId(res.job_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not regenerate the section");
    }
  }

  return (
    <div className="mx-auto my-auto w-full max-w-3xl px-8 py-10">
      <header className="mb-8">
        <p className="font-mono text-xs uppercase tracking-widest text-foreground-secondary">
          Generate
        </p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">
          Describe a song, hear it in your voice
        </h1>
      </header>

      {!backendReady && (
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-accent/30 bg-accent/5 px-4 py-3 text-sm">
          <div>
            <p className="font-medium">One more step before you can generate</p>
            <p className="mt-1 leading-relaxed text-foreground-secondary">
              The AI models aren&apos;t installed yet — a one-time setup puts them in place.
            </p>
          </div>
          <button
            onClick={() => setGuideOpen(true)}
            className="h-9 shrink-0 rounded-lg bg-accent px-4 text-sm font-medium text-white"
          >
            See what&apos;s missing
          </button>
        </div>
      )}
      <SetupGuide open={guideOpen} onClose={() => setGuideOpen(false)} />

      {welcome && backendReady && (
        <div className="mb-6 flex items-center justify-between gap-3 rounded-xl border border-success/30 bg-success/5 px-4 py-3 text-sm">
          <p>
            <span className="font-medium">You&apos;re good to go</span> — everything&apos;s
            installed. Describe a song and hit Generate, or train a voice first.
          </p>
          <button
            onClick={() => setWelcome(false)}
            aria-label="Dismiss"
            className="shrink-0 rounded-lg p-1 text-foreground-secondary hover:text-foreground"
          >
            ✕
          </button>
        </div>
      )}

      {error && (
        <div className="mb-6 rounded-xl border border-error/30 bg-error/5 px-4 py-3 text-sm text-error">
          {error}
        </div>
      )}

      {/* input mode tabs */}
      <div className="mb-3 flex gap-1 rounded-full border border-border bg-surface p-1 text-sm font-medium w-fit">
        <TabButton active={mode === "prompt"} onClick={() => switchMode("prompt")}>
          Describe it
        </TabButton>
        <TabButton active={mode === "lyrics"} onClick={() => switchMode("lyrics")}>
          Your lyrics
        </TabButton>
      </div>

      {mode === "prompt" ? (
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="A slow bossa nova about rain on the window, in Portuguese…"
          rows={3}
          disabled={running}
          className="w-full resize-none rounded-2xl border border-border bg-surface px-5 py-4 text-lg leading-relaxed outline-none transition-colors focus:border-accent disabled:opacity-60"
        />
      ) : (
        <div>
          <div className="mb-1.5 flex items-center justify-between">
            <p className="text-xs text-foreground-secondary">
              Sung exactly as written — shape it with{" "}
              <span className="font-mono">[Verse]</span>,{" "}
              <span className="font-mono">[Chorus]</span>,{" "}
              <span className="font-mono">[Bridge]</span> tags.
            </p>
            <button
              onClick={() => setLyrics(EXAMPLE_LYRICS)}
              disabled={running}
              className="font-mono text-xs text-accent hover:underline"
            >
              Insert example
            </button>
          </div>
          <textarea
            value={lyrics}
            onChange={(e) => setLyrics(e.target.value)}
            placeholder={"[Verse]\nYour first line here…\n\n[Chorus]\nThe hook you want remembered"}
            rows={10}
            disabled={running}
            className="w-full resize-y rounded-2xl border border-border bg-surface px-5 py-4 font-mono text-sm leading-relaxed outline-none transition-colors focus:border-accent disabled:opacity-60"
          />
          <input
            type="text"
            value={styleText}
            onChange={(e) => setStyleText(e.target.value)}
            disabled={running}
            placeholder="Style: dreamy synth-pop, 100 bpm, warm vocals, English"
            className="mt-2 w-full rounded-xl border border-border bg-surface px-4 py-2.5 text-sm outline-none transition-colors focus:border-accent disabled:opacity-60"
          />
          <p className="mt-1.5 text-xs leading-relaxed text-foreground-secondary">
            Keep lines short and singable and repeat the chorus word-for-word. Genre, tempo, and
            instruments go in the style line — the model reads section tags, not chords. Set
            Length to <em>Auto</em> under Advanced and the song sizes itself to your lyrics.
          </p>
        </div>
      )}

      {/* voice + generate row */}
      <div className="mt-4 flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-mono text-xs uppercase tracking-widest text-foreground-secondary">
            Voice
          </span>
          {ready.map((p) => (
            <VoiceChip key={p.id} label={p.name} active={voiceId === p.id} onClick={() => setVoiceId(p.id)} />
          ))}
          {ready.length === 0 && (
            <button
              onClick={goToVoice}
              className="rounded-full border border-border px-3 py-1.5 text-sm text-foreground-secondary hover:border-accent hover:text-accent"
            >
              Train a voice →
            </button>
          )}
          <VoiceChip label="Male" active={voiceId === "male"} onClick={() => setVoiceId("male")} />
          <VoiceChip
            label="Female"
            active={voiceId === "female"}
            onClick={() => setVoiceId("female")}
          />
          {mode === "prompt" && (
            <VoiceChip
              label="Instrumental"
              active={instrumental}
              onClick={() => setVoiceId("instrumental")}
            />
          )}
        </div>

        <button
          onClick={onGenerate}
          disabled={busy || running || !canGenerate}
          className="inline-flex h-12 items-center justify-center rounded-full bg-accent px-8 text-sm font-medium text-white transition-opacity disabled:cursor-not-allowed disabled:opacity-40"
        >
          {running ? "Generating…" : "Generate"}
        </button>
      </div>

      {/* advanced */}
      <div className="mt-4">
        <button
          onClick={() => setAdvanced((a) => !a)}
          className="font-mono text-xs uppercase tracking-widest text-foreground-secondary hover:text-foreground"
        >
          {advanced ? "− Advanced" : "+ Advanced"}
        </button>
        {advanced && (
          <div className="mt-3 flex flex-col gap-4 rounded-xl border border-border bg-surface px-4 py-4">
            <div>
              <div className="flex items-center gap-3">
                <label className="text-sm text-foreground-secondary">Length</label>
                <select
                  value={duration}
                  onChange={(e) =>
                    setDuration(e.target.value === "auto" ? "auto" : Number(e.target.value))
                  }
                  disabled={running}
                  className="rounded-lg border border-border bg-background px-3 py-1.5 text-sm outline-none focus:border-accent"
                >
                  <option value="auto">Auto · match the lyrics</option>
                  {[15, 30, 60, 90, 120, 180, 240, 300].map((s) => (
                    <option key={s} value={s}>
                      {s < 60 ? `${s}s` : `${Math.floor(s / 60)}m${s % 60 ? ` ${s % 60}s` : ""}`}
                    </option>
                  ))}
                </select>
              </div>
              {duration === "auto" && (
                <p className="mt-1.5 text-xs leading-relaxed text-foreground-secondary">
                  The model sizes the song to the lyrics — a four-minute lyric gets a
                  four-minute track. More sections, longer song.
                </p>
              )}
            </div>

            <div>
              <label className="text-sm text-foreground-secondary">Save to (optional)</label>
              <input
                type="text"
                value={outputDir}
                onChange={(e) => setOutputDir(e.target.value)}
                disabled={running}
                placeholder="Leave empty for the Cadence library folder, or paste one like D:\Music\Drafts"
                className="mt-1.5 w-full rounded-lg border border-border bg-background px-3 py-2 font-mono text-sm outline-none focus:border-accent"
              />
            </div>

            <label className="flex items-start gap-2.5 text-sm">
              <input
                type="checkbox"
                checked={saveStems}
                onChange={(e) => setSaveStems(e.target.checked)}
                disabled={running}
                className="mt-0.5 h-4 w-4 accent-accent"
              />
              <span>
                Save stems separately
                <span className="block text-xs leading-relaxed text-foreground-secondary">
                  Also writes <span className="font-mono">.vocals.wav</span> and{" "}
                  <span className="font-mono">.instrumental.wav</span> next to the track. Needs
                  the voice backend; on instrumental tracks the vocal stem is near-silent.
                </span>
              </span>
            </label>

          </div>
        )}
      </div>

      {/* status */}
      {jobId && job && job.status !== "done" && (
        <StatusCard job={job} instrumental={repainting || instrumental || genericVoice} />
      )}
      {job?.status === "error" && (
        <div className="mt-6 rounded-2xl border border-error/30 bg-error/5 p-5 text-sm text-error">
          {job.error ?? "Generation failed."}
        </div>
      )}

      {/* result */}
      {track && <Result track={track} onRepaint={running ? undefined : startRepaint} />}
    </div>
  );
}

function StatusCard({ job, instrumental }: { job: Job; instrumental: boolean }) {
  const steps = instrumental ? STEPS_INSTRUMENTAL : STEPS_VOICE;
  const current = stepIndex(job.detail);
  return (
    <div className="mt-6 rounded-2xl border border-border bg-surface p-6">
      <div className="flex flex-col gap-3">
        {steps.map((label, i) => {
          const state = i < current ? "done" : i === current ? "active" : "todo";
          return (
            <div key={label} className="flex items-center gap-3">
              <span
                className={`flex h-5 w-5 items-center justify-center rounded-full text-[0.6rem] ${
                  state === "done"
                    ? "bg-success text-white"
                    : state === "active"
                      ? "bg-accent text-white"
                      : "border border-border text-foreground-secondary"
                }`}
              >
                {state === "done" ? "✓" : i + 1}
              </span>
              <span
                className={`text-sm ${
                  state === "todo" ? "text-foreground-secondary" : "text-foreground"
                }`}
              >
                {label}
              </span>
              {state === "active" && (
                <span className="ml-1 h-3.5 w-3.5 animate-spin rounded-full border-2 border-border border-t-accent" />
              )}
            </div>
          );
        })}
      </div>
      <p className="mt-4 font-mono text-xs text-foreground-secondary">{job.detail}</p>
    </div>
  );
}

function Result({
  track,
  onRepaint,
}: {
  track: Track;
  onRepaint?: (trackId: string, start: number, end: number, part: string) => void;
}) {
  const [dur, setDur] = useState(0);
  const [open, setOpen] = useState(false);
  const [start, setStart] = useState(0);
  const [end, setEnd] = useState(15);
  const [part, setPart] = useState("");
  const isInstrumental = track.instrumental === 1;

  function onLoaded(e: React.SyntheticEvent<HTMLAudioElement>) {
    const d = Math.floor(e.currentTarget.duration || 0);
    if (d > 0) {
      setDur(d);
      setEnd((prev) => (prev === 15 ? Math.min(15, d) : Math.min(prev, d)));
    }
  }

  const validRange = end > start && end <= (dur || end);

  return (
    <div className="mt-6 rounded-2xl border border-border bg-surface p-6">
      <div className="mb-3 flex items-center gap-2">
        <span className="rounded-full border border-success/40 bg-success/5 px-2.5 py-0.5 font-mono text-[0.65rem] uppercase tracking-wider text-success">
          Done
        </span>
        {track.voice_name && (
          <span className="font-mono text-xs text-foreground-secondary">
            voice · {track.voice_name}
          </span>
        )}
        {track.vocal_language && (
          <span className="font-mono text-xs text-foreground-secondary">
            {track.vocal_language}
            {track.bpm ? ` · ${track.bpm} bpm` : ""}
          </span>
        )}
      </div>
      {track.caption && <p className="mb-4 text-sm text-foreground-secondary">{track.caption}</p>}
      <audio controls src={trackAudioUrl(track.id)} onLoadedMetadata={onLoaded} className="w-full" />
      {track.lyrics && (
        <pre className="mt-4 max-h-64 overflow-y-auto whitespace-pre-wrap border-t border-border pt-4 font-sans text-sm leading-relaxed text-foreground-secondary">
          {track.lyrics}
        </pre>
      )}

      {onRepaint && isInstrumental && (
        <div className="mt-4 border-t border-border pt-4">
          <button
            onClick={() => setOpen((o) => !o)}
            className="font-mono text-xs uppercase tracking-widest text-foreground-secondary hover:text-foreground"
          >
            {open ? "− Regenerate a part" : "+ Regenerate a part"}
          </button>
          {open && (
            <div className="mt-3 flex flex-col gap-3">
              <p className="text-xs leading-relaxed text-foreground-secondary">
                Keep the rest of the track, regenerate just this time range. Play it to find the
                seconds you want{dur ? ` (track is ${dur}s)` : ""}.
              </p>
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <label className="text-foreground-secondary">From</label>
                <input
                  type="number"
                  min={0}
                  max={dur || undefined}
                  value={start}
                  onChange={(e) => setStart(Math.max(0, Number(e.target.value)))}
                  className="h-9 w-20 rounded-lg border border-border bg-background px-2.5 outline-none focus:border-accent"
                />
                <label className="text-foreground-secondary">to</label>
                <input
                  type="number"
                  min={0}
                  max={dur || undefined}
                  value={end}
                  onChange={(e) => setEnd(Math.max(0, Number(e.target.value)))}
                  className="h-9 w-20 rounded-lg border border-border bg-background px-2.5 outline-none focus:border-accent"
                />
                <span className="text-foreground-secondary">seconds</span>
              </div>
              <input
                type="text"
                value={part}
                onChange={(e) => setPart(e.target.value)}
                placeholder="Optional: a new direction for this part, e.g. add a piano solo"
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-accent"
              />
              <button
                onClick={() => onRepaint(track.id, start, end, part)}
                disabled={!validRange}
                className="h-10 w-fit rounded-full bg-accent px-6 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-40"
              >
                Regenerate {start}s–{end}s
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`rounded-full px-4 py-1.5 transition-colors ${
        active
          ? "bg-accent text-white"
          : "text-foreground-secondary hover:text-foreground"
      }`}
    >
      {children}
    </button>
  );
}

function VoiceChip({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`rounded-full border px-3 py-1.5 text-sm transition-colors ${
        active
          ? "border-accent bg-accent/5 text-foreground"
          : "border-border text-foreground-secondary hover:border-foreground-secondary"
      }`}
    >
      {label}
    </button>
  );
}
