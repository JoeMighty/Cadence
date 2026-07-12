"use client";

import { useCallback, useEffect, useState } from "react";
import {
  deleteTrack,
  listTracks,
  trackAudioUrl,
  trackExportUrl,
  type Track,
} from "@/lib/engine";
import Loading from "@/components/Loading";

function when(ts: number): string {
  return new Date(ts * 1000).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function Library({ goToGenerate }: { goToGenerate: () => void }) {
  const [tracks, setTracks] = useState<Track[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setTracks(await listTracks());
    } catch {
      setError("Engine offline. Start the engine, then reload.");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function remove(id: string) {
    setTracks((prev) => prev?.filter((t) => t.id !== id) ?? prev);
    try {
      await deleteTrack(id);
    } catch {
      load();
    }
  }

  return (
    <div className="mx-auto w-full max-w-3xl px-8 py-10">
      <header className="mb-8">
        <p className="font-mono text-xs uppercase tracking-widest text-foreground-secondary">
          Library
        </p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">Everything you&apos;ve made</h1>
      </header>

      {error && (
        <div className="mb-6 rounded-xl border border-error/30 bg-error/5 px-4 py-3 text-sm text-error">
          {error}
        </div>
      )}

      {tracks === null && !error && <Loading />}

      {tracks && tracks.length === 0 && !error && (
        <div className="rounded-2xl border border-dashed border-border bg-surface p-10 text-center">
          <p className="text-foreground-secondary">No tracks yet.</p>
          <button
            onClick={goToGenerate}
            className="mt-4 inline-flex h-10 items-center rounded-full bg-accent px-5 text-sm font-medium text-white"
          >
            Generate your first
          </button>
        </div>
      )}

      <div className="flex flex-col gap-4">
        {tracks?.map((t) => (
          <TrackCard key={t.id} track={t} onDelete={() => remove(t.id)} />
        ))}
      </div>
    </div>
  );
}

function TrackCard({ track, onDelete }: { track: Track; onDelete: () => void }) {
  const [confirming, setConfirming] = useState(false);
  const title = track.prompt || track.caption || "Untitled";

  useEffect(() => {
    if (!confirming) return;
    const id = setTimeout(() => setConfirming(false), 3000);
    return () => clearTimeout(id);
  }, [confirming]);

  return (
    <div className="rounded-2xl border border-border bg-surface p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h3 className="truncate font-medium">{title}</h3>
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-xs text-foreground-secondary">
            <span>{when(track.created_at)}</span>
            {track.instrumental ? (
              <span>instrumental</span>
            ) : (
              track.voice_name && <span>voice · {track.voice_name}</span>
            )}
            {track.vocal_language && <span>{track.vocal_language}</span>}
            {track.bpm ? <span>{track.bpm} bpm</span> : null}
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <a
            href={trackExportUrl(track.id, "wav")}
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-lg border border-border px-3 py-1.5 text-xs font-medium hover:border-accent hover:text-accent"
          >
            WAV
          </a>
          <a
            href={trackExportUrl(track.id, "mp3")}
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-lg border border-border px-3 py-1.5 text-xs font-medium hover:border-accent hover:text-accent"
          >
            MP3
          </a>
          {confirming ? (
            <button
              onClick={onDelete}
              className="rounded-lg bg-error px-3 py-1.5 text-xs font-medium text-white"
            >
              Confirm
            </button>
          ) : (
            <button
              onClick={() => setConfirming(true)}
              className="rounded-lg border border-border px-3 py-1.5 text-xs text-foreground-secondary hover:border-error hover:text-error"
            >
              Delete
            </button>
          )}
        </div>
      </div>

      <audio controls src={trackAudioUrl(track.id)} className="mt-4 w-full" />

      {track.lyrics && (
        <details className="mt-3">
          <summary className="cursor-pointer font-mono text-xs uppercase tracking-widest text-foreground-secondary">
            Lyrics
          </summary>
          <pre className="mt-2 max-h-56 overflow-y-auto whitespace-pre-wrap border-t border-border pt-3 font-sans text-sm leading-relaxed text-foreground-secondary">
            {track.lyrics}
          </pre>
        </details>
      )}
    </div>
  );
}
