"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  createProfile,
  deleteProfile,
  getProfile,
  listProfiles,
  trainVoice,
  uploadTake,
  type VoiceProfile,
} from "@/lib/engine";
import { Recorder } from "@/lib/recorder";
import { READING_SCRIPT } from "@/lib/script";

function fmt(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

type Pending = { blob: Blob; seconds: number; url: string };

export default function VoiceSetup() {
  const [profiles, setProfiles] = useState<VoiceProfile[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [newName, setNewName] = useState("");
  const [scriptIndex, setScriptIndex] = useState(0);
  const [recording, setRecording] = useState(false);
  const [level, setLevel] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const [pending, setPending] = useState<Pending | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const recorder = useRef<Recorder | null>(null);
  const elapsedTimer = useRef<ReturnType<typeof setInterval> | null>(null);

  const active = profiles.find((p) => p.id === activeId) ?? null;

  const refreshProfiles = useCallback(async () => {
    try {
      const list = await listProfiles();
      setProfiles(list);
      return list;
    } catch {
      setError("Engine offline. Start the engine, then reload.");
      return [];
    }
  }, []);

  useEffect(() => {
    refreshProfiles().then((list) => {
      if (list.length && !activeId) setActiveId(list[0].id);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Poll while a voice is training so progress stays live.
  useEffect(() => {
    if (active?.status !== "training") return;
    const id = setInterval(async () => {
      try {
        const p = await getProfile(active.id);
        setProfiles((prev) => prev.map((x) => (x.id === p.id ? p : x)));
      } catch {
        /* transient */
      }
    }, 2000);
    return () => clearInterval(id);
  }, [active?.status, active?.id]);

  async function handleCreate() {
    const name = newName.trim();
    if (!name) return;
    setBusy(true);
    setError(null);
    try {
      const p = await createProfile(name);
      setProfiles((prev) => [p, ...prev]);
      setActiveId(p.id);
      setNewName("");
      setScriptIndex(0);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not create voice");
    } finally {
      setBusy(false);
    }
  }

  async function startRecording() {
    setError(null);
    try {
      recorder.current = new Recorder();
      await recorder.current.start(setLevel);
      setRecording(true);
      setElapsed(0);
      elapsedTimer.current = setInterval(() => setElapsed((e) => e + 0.1), 100);
    } catch {
      setError("Microphone unavailable. Check your input device and permissions.");
      recorder.current = null;
    }
  }

  async function stopRecording() {
    if (!recorder.current) return;
    if (elapsedTimer.current) clearInterval(elapsedTimer.current);
    const result = await recorder.current.stop();
    recorder.current = null;
    setRecording(false);
    setLevel(0);
    setPending({ ...result, url: URL.createObjectURL(result.blob) });
  }

  async function keepTake() {
    if (!pending || !active) return;
    setBusy(true);
    try {
      const { profile } = await uploadTake(active.id, pending.blob, scriptIndex);
      setProfiles((prev) => prev.map((p) => (p.id === profile.id ? profile : p)));
      URL.revokeObjectURL(pending.url);
      setPending(null);
      setScriptIndex((i) => (i + 1) % READING_SCRIPT.length);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  function redoTake() {
    if (pending) URL.revokeObjectURL(pending.url);
    setPending(null);
  }

  async function handleTrain() {
    if (!active) return;
    setBusy(true);
    setError(null);
    try {
      await trainVoice(active.id);
      const p = await getProfile(active.id);
      setProfiles((prev) => prev.map((x) => (x.id === p.id ? p : x)));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not start training");
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete(id: string) {
    await deleteProfile(id);
    const list = await refreshProfiles();
    if (activeId === id) setActiveId(list[0]?.id ?? null);
  }

  return (
    <div className="mx-auto w-full max-w-3xl px-8 py-10">
      <header className="mb-8">
        <p className="font-mono text-xs uppercase tracking-widest text-foreground-secondary">
          Voice Setup
        </p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">
          Train Cadence on your voice
        </h1>
        <p className="mt-2 max-w-xl text-foreground-secondary">
          Read the lines aloud in short takes. Once there are a few minutes of clean
          speech, training unlocks and every track will sing in this voice.
        </p>
      </header>

      {error && (
        <div className="mb-6 rounded-xl border border-error/30 bg-error/5 px-4 py-3 text-sm text-error">
          {error}
        </div>
      )}

      {/* voice selector */}
      <div className="mb-8 flex flex-wrap items-center gap-2">
        {profiles.map((p) => (
          <button
            key={p.id}
            onClick={() => {
              setActiveId(p.id);
              setPending(null);
            }}
            className={`flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm transition-colors ${
              p.id === activeId
                ? "border-accent bg-accent/5 text-foreground"
                : "border-border text-foreground-secondary hover:border-foreground-secondary"
            }`}
          >
            <StatusDot status={p.status} />
            {p.name}
          </button>
        ))}
        <NewVoiceInput
          value={newName}
          onChange={setNewName}
          onCreate={handleCreate}
          busy={busy}
        />
      </div>

      {!active ? (
        <EmptyState />
      ) : active.status === "training" ? (
        <TrainingCard profile={active} />
      ) : (
        <>
          <ProfilePanel profile={active} onTrain={handleTrain} busy={busy} onDelete={handleDelete} />
          <RecordingPanel
            scriptIndex={scriptIndex}
            onSkip={() => setScriptIndex((i) => (i + 1) % READING_SCRIPT.length)}
            recording={recording}
            level={level}
            elapsed={elapsed}
            pending={pending}
            onStart={startRecording}
            onStop={stopRecording}
            onKeep={keepTake}
            onRedo={redoTake}
            busy={busy}
          />
        </>
      )}
    </div>
  );
}

function ProfilePanel({
  profile,
  onTrain,
  onDelete,
  busy,
}: {
  profile: VoiceProfile;
  onTrain: () => void;
  onDelete: (id: string) => void;
  busy: boolean;
}) {
  const pct = Math.min(100, (profile.total_seconds / profile.unlock_seconds) * 100);
  return (
    <div className="mb-6 rounded-2xl border border-border bg-surface p-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold">{profile.name}</h2>
          <StatusBadge status={profile.status} />
        </div>
        <button
          onClick={() => onDelete(profile.id)}
          className="text-xs text-foreground-secondary hover:text-error"
        >
          Delete
        </button>
      </div>

      <div className="mt-4">
        <div className="mb-1.5 flex justify-between font-mono text-xs text-foreground-secondary">
          <span>{fmt(profile.total_seconds)} collected</span>
          <span>{fmt(profile.unlock_seconds)} to unlock</span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-border">
          <div
            className={`h-full rounded-full transition-all ${
              profile.can_train ? "bg-success" : "bg-accent"
            }`}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      <button
        onClick={onTrain}
        disabled={!profile.can_train || busy}
        className="mt-5 inline-flex h-11 items-center justify-center rounded-full bg-accent px-6 text-sm font-medium text-white transition-opacity disabled:cursor-not-allowed disabled:opacity-40"
      >
        {profile.status === "ready" ? "Retrain voice" : "Train voice"}
      </button>
      {!profile.can_train && (
        <span className="ml-3 text-sm text-foreground-secondary">
          Record more to unlock training.
        </span>
      )}
      {profile.status === "error" && profile.error && (
        <p className="mt-3 text-sm text-error">{profile.error}</p>
      )}
    </div>
  );
}

function RecordingPanel(props: {
  scriptIndex: number;
  onSkip: () => void;
  recording: boolean;
  level: number;
  elapsed: number;
  pending: Pending | null;
  onStart: () => void;
  onStop: () => void;
  onKeep: () => void;
  onRedo: () => void;
  busy: boolean;
}) {
  const { scriptIndex, onSkip, recording, level, elapsed, pending } = props;
  return (
    <div className="rounded-2xl border border-border bg-surface p-6">
      <div className="mb-1 flex items-center justify-between">
        <p className="font-mono text-xs uppercase tracking-widest text-foreground-secondary">
          Read this aloud · {scriptIndex + 1} / {READING_SCRIPT.length}
        </p>
        {!recording && !pending && (
          <button onClick={onSkip} className="text-xs text-foreground-secondary hover:text-foreground">
            Skip line
          </button>
        )}
      </div>
      <p className="min-h-[4.5rem] text-xl leading-relaxed tracking-tight">
        {READING_SCRIPT[scriptIndex]}
      </p>

      {pending ? (
        <div className="mt-4">
          <audio controls src={pending.url} className="w-full" />
          <div className="mt-4 flex gap-3">
            <button
              onClick={props.onKeep}
              disabled={props.busy}
              className="inline-flex h-11 items-center justify-center rounded-full bg-success px-6 text-sm font-medium text-white disabled:opacity-40"
            >
              Keep take ({fmt(pending.seconds)})
            </button>
            <button
              onClick={props.onRedo}
              className="inline-flex h-11 items-center justify-center rounded-full border border-border px-6 text-sm font-medium hover:border-foreground-secondary"
            >
              Redo
            </button>
          </div>
        </div>
      ) : (
        <div className="mt-4">
          {recording && <LevelMeter level={level} elapsed={elapsed} />}
          <button
            onClick={recording ? props.onStop : props.onStart}
            className={`mt-4 inline-flex h-12 items-center gap-2.5 rounded-full px-7 text-sm font-medium text-white transition-colors ${
              recording ? "bg-error" : "bg-accent"
            }`}
          >
            <span className={`h-2.5 w-2.5 rounded-full bg-white ${recording ? "animate-pulse" : ""}`} />
            {recording ? "Stop recording" : "Record"}
          </button>
        </div>
      )}
    </div>
  );
}

function LevelMeter({ level, elapsed }: { level: number; elapsed: number }) {
  const pct = Math.min(100, level * 110);
  let label = "Good level";
  let color = "bg-success";
  if (level < 0.05) {
    label = "Too quiet — move closer";
    color = "bg-foreground-secondary";
  } else if (level >= 0.98) {
    label = "Clipping — ease back";
    color = "bg-error";
  } else if (level >= 0.9) {
    label = "A little loud";
    color = "bg-accent";
  }
  return (
    <div>
      <div className="mb-1.5 flex justify-between font-mono text-xs text-foreground-secondary">
        <span>{label}</span>
        <span>{fmt(elapsed)}</span>
      </div>
      <div className="h-2.5 overflow-hidden rounded-full bg-border">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function TrainingCard({ profile }: { profile: VoiceProfile }) {
  return (
    <div className="rounded-2xl border border-border bg-surface p-8 text-center">
      <div className="mx-auto mb-4 h-8 w-8 animate-spin rounded-full border-2 border-border border-t-accent" />
      <h2 className="text-lg font-semibold">Training {profile.name}</h2>
      <p className="mt-2 font-mono text-sm text-foreground-secondary">
        {profile.detail ?? "Working…"}
      </p>
      <p className="mt-4 text-sm text-foreground-secondary">
        This runs on your GPU and can take a while. You can leave this screen; it keeps going.
      </p>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="rounded-2xl border border-dashed border-border bg-surface p-10 text-center">
      <p className="text-foreground-secondary">
        Name a voice above to start recording.
      </p>
    </div>
  );
}

function NewVoiceInput({
  value,
  onChange,
  onCreate,
  busy,
}: {
  value: string;
  onChange: (v: string) => void;
  onCreate: () => void;
  busy: boolean;
}) {
  return (
    <div className="flex items-center gap-1.5">
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && onCreate()}
        placeholder="New voice…"
        className="h-9 w-32 rounded-full border border-border bg-background px-3.5 text-sm outline-none focus:border-accent"
      />
      <button
        onClick={onCreate}
        disabled={busy || !value.trim()}
        className="flex h-9 w-9 items-center justify-center rounded-full border border-border text-foreground-secondary transition-colors hover:border-accent hover:text-accent disabled:opacity-40"
        aria-label="Create voice"
      >
        +
      </button>
    </div>
  );
}

function StatusBadge({ status }: { status: VoiceProfile["status"] }) {
  const map: Record<VoiceProfile["status"], [string, string]> = {
    collecting: ["Collecting", "text-foreground-secondary border-border"],
    training: ["Training", "text-accent border-accent/40 bg-accent/5"],
    ready: ["Ready", "text-success border-success/40 bg-success/5"],
    error: ["Error", "text-error border-error/40 bg-error/5"],
  };
  const [label, cls] = map[status];
  return (
    <span className={`rounded-full border px-2.5 py-0.5 font-mono text-[0.65rem] uppercase tracking-wider ${cls}`}>
      {label}
    </span>
  );
}

function StatusDot({ status }: { status: VoiceProfile["status"] }) {
  const color =
    status === "ready"
      ? "bg-success"
      : status === "training"
        ? "bg-accent"
        : status === "error"
          ? "bg-error"
          : "bg-foreground-secondary";
  return <span className={`h-2 w-2 rounded-full ${color}`} />;
}
