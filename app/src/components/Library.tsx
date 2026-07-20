"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  deleteTrack,
  listTracks,
  setTrackLiked,
  trackExportUrl,
  type Track,
} from "@/lib/engine";
import { usePlayer } from "@/lib/player";
import Loading from "@/components/Loading";

function when(ts: number): string {
  return new Date(ts * 1000).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function Library({
  goToGenerate,
  onRemix,
}: {
  goToGenerate: () => void;
  onRemix: (track: Track) => void;
}) {
  const player = usePlayer();
  const [tracks, setTracks] = useState<Track[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [favOnly, setFavOnly] = useState(false);

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

  const visible = useMemo(() => {
    if (!tracks) return [];
    const q = query.trim().toLowerCase();
    return tracks.filter((t) => {
      if (favOnly && !t.liked) return false;
      if (!q) return true;
      return `${t.prompt} ${t.caption ?? ""} ${t.voice_name ?? ""} ${t.lyrics ?? ""}`
        .toLowerCase()
        .includes(q);
    });
  }, [tracks, query, favOnly]);

  const likedCount = tracks?.filter((t) => t.liked).length ?? 0;

  async function remove(id: string) {
    setTracks((prev) => prev?.filter((t) => t.id !== id) ?? prev);
    try {
      await deleteTrack(id);
    } catch {
      load();
    }
  }

  async function toggleLike(track: Track) {
    const liked = track.liked ? 0 : 1;
    setTracks((prev) => prev?.map((t) => (t.id === track.id ? { ...t, liked } : t)) ?? prev);
    try {
      await setTrackLiked(track.id, !!liked);
    } catch {
      load();
    }
  }

  const empty = tracks && tracks.length === 0;

  return (
    <div className="mx-auto w-full max-w-3xl px-8 py-10">
      <header className="mb-6">
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

      {empty && !error && (
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

      {tracks && tracks.length > 0 && (
        <>
          <div className="mb-5 flex flex-wrap items-center gap-2">
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search prompts, lyrics, voices…"
              className="h-9 flex-1 rounded-lg border border-border bg-surface px-3.5 text-sm outline-none focus:border-accent"
            />
            <FilterChip active={!favOnly} onClick={() => setFavOnly(false)}>
              All {tracks.length}
            </FilterChip>
            <FilterChip active={favOnly} onClick={() => setFavOnly(true)}>
              ♥ {likedCount}
            </FilterChip>
          </div>

          {visible.length === 0 ? (
            <p className="rounded-xl border border-dashed border-border bg-surface px-4 py-8 text-center text-sm text-foreground-secondary">
              {favOnly ? "No favorites yet — tap the heart on a track." : "Nothing matches that search."}
            </p>
          ) : (
            <div className="flex flex-col gap-3">
              {visible.map((t) => (
                <TrackCard
                  key={t.id}
                  track={t}
                  current={player.current?.id === t.id}
                  playing={player.current?.id === t.id && player.isPlaying}
                  onPlay={() =>
                    player.current?.id === t.id ? player.toggle() : player.play(t, visible)
                  }
                  onLike={() => toggleLike(t)}
                  onRemix={() => onRemix(t)}
                  onDelete={() => remove(t.id)}
                />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

function FilterChip({
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
      className={`h-9 rounded-lg border px-3 text-sm transition-colors ${
        active
          ? "border-accent bg-accent/5 text-foreground"
          : "border-border text-foreground-secondary hover:border-foreground-secondary"
      }`}
    >
      {children}
    </button>
  );
}

function TrackCard({
  track,
  current,
  playing,
  onPlay,
  onLike,
  onRemix,
  onDelete,
}: {
  track: Track;
  current: boolean;
  playing: boolean;
  onPlay: () => void;
  onLike: () => void;
  onRemix: () => void;
  onDelete: () => void;
}) {
  const [confirming, setConfirming] = useState(false);
  const title = track.prompt || track.caption || "Untitled";

  useEffect(() => {
    if (!confirming) return;
    const id = setTimeout(() => setConfirming(false), 3000);
    return () => clearTimeout(id);
  }, [confirming]);

  return (
    <div
      className={`rounded-2xl border bg-surface p-4 transition-colors ${
        current ? "border-accent/50" : "border-border"
      }`}
    >
      <div className="flex items-center gap-4">
        <button
          onClick={onPlay}
          aria-label={playing ? "Pause" : "Play"}
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-accent text-white"
        >
          {playing ? (
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
              <path d="M6 5h4v14H6zm8 0h4v14h-4z" />
            </svg>
          ) : (
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
              <path d="M8 5v14l11-7z" />
            </svg>
          )}
        </button>

        <div className="min-w-0 flex-1">
          <h3 className="truncate font-medium">{title}</h3>
          <div className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-0.5 font-mono text-xs text-foreground-secondary">
            <span>{when(track.created_at)}</span>
            {track.instrumental ? (
              <span>instrumental</span>
            ) : (
              track.voice_name && <span>voice · {track.voice_name}</span>
            )}
            {track.bpm ? <span>{track.bpm} bpm</span> : null}
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-1.5">
          <button
            onClick={onLike}
            aria-label={track.liked ? "Unfavorite" : "Favorite"}
            className={`flex h-8 w-8 items-center justify-center rounded-lg transition-colors ${
              track.liked
                ? "text-accent"
                : "text-foreground-secondary hover:bg-background hover:text-foreground"
            }`}
          >
            <svg width="17" height="17" viewBox="0 0 24 24" fill={track.liked ? "currentColor" : "none"} stroke="currentColor" strokeWidth="1.8">
              <path d="M12 21s-7-4.35-9.5-8.5C1 9.5 2.5 6 6 6c2 0 3.2 1.2 4 2.3C10.8 7.2 12 6 14 6c3.5 0 5 3.5 3.5 6.5C19 16.65 12 21 12 21z" />
            </svg>
          </button>
          <button
            onClick={onRemix}
            className="rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-foreground-secondary hover:border-accent hover:text-accent"
          >
            Remix
          </button>
          <MenuActions track={track} confirming={confirming} setConfirming={setConfirming} onDelete={onDelete} />
        </div>
      </div>

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

function MenuActions({
  track,
  confirming,
  setConfirming,
  onDelete,
}: {
  track: Track;
  confirming: boolean;
  setConfirming: (v: boolean) => void;
  onDelete: () => void;
}) {
  return (
    <div className="flex items-center gap-1.5">
      <a
        href={trackExportUrl(track.id, "wav")}
        target="_blank"
        rel="noopener noreferrer"
        className="rounded-lg border border-border px-2.5 py-1.5 text-xs font-medium hover:border-accent hover:text-accent"
      >
        WAV
      </a>
      <a
        href={trackExportUrl(track.id, "mp3")}
        target="_blank"
        rel="noopener noreferrer"
        className="rounded-lg border border-border px-2.5 py-1.5 text-xs font-medium hover:border-accent hover:text-accent"
      >
        MP3
      </a>
      {confirming ? (
        <button
          onClick={onDelete}
          className="rounded-lg bg-error px-2.5 py-1.5 text-xs font-medium text-white"
        >
          Confirm
        </button>
      ) : (
        <button
          onClick={() => setConfirming(true)}
          className="rounded-lg border border-border px-2.5 py-1.5 text-xs text-foreground-secondary hover:border-error hover:text-error"
        >
          Delete
        </button>
      )}
    </div>
  );
}
