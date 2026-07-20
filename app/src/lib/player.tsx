"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { trackAudioUrl, type Track } from "@/lib/engine";

interface PlayerApi {
  current: Track | null;
  isPlaying: boolean;
  progress: number; // 0..1
  duration: number; // seconds
  time: number; // seconds
  play: (track: Track, queue?: Track[]) => void;
  toggle: () => void;
  next: () => void;
  prev: () => void;
  seek: (fraction: number) => void;
  close: () => void;
  hasNext: boolean;
  hasPrev: boolean;
}

const PlayerContext = createContext<PlayerApi | null>(null);

export function usePlayer(): PlayerApi {
  const ctx = useContext(PlayerContext);
  if (!ctx) throw new Error("usePlayer must be used within PlayerProvider");
  return ctx;
}

export function PlayerProvider({ children }: { children: ReactNode }) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const queueRef = useRef<Track[]>([]);
  const indexRef = useRef(-1);
  const [current, setCurrent] = useState<Track | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [progress, setProgress] = useState(0);
  const [duration, setDuration] = useState(0);
  const [time, setTime] = useState(0);
  const [hasNext, setHasNext] = useState(false);
  const [hasPrev, setHasPrev] = useState(false);

  const goto = useCallback((i: number) => {
    const q = queueRef.current;
    if (i < 0 || i >= q.length) return;
    indexRef.current = i;
    const track = q[i];
    setCurrent(track);
    setHasPrev(i > 0);
    setHasNext(i < q.length - 1);
    setProgress(0);
    setTime(0);
    const a = audioRef.current;
    if (a) {
      a.src = trackAudioUrl(track.id);
      a.currentTime = 0;
      a.play().catch(() => {});
    }
  }, []);

  useEffect(() => {
    const a = new Audio();
    audioRef.current = a;
    const onTime = () => {
      setTime(a.currentTime);
      setProgress(a.duration ? a.currentTime / a.duration : 0);
    };
    const onMeta = () => setDuration(a.duration || 0);
    const onPlay = () => setIsPlaying(true);
    const onPause = () => setIsPlaying(false);
    const onEnded = () => goto(indexRef.current + 1); // advance if there's a next
    a.addEventListener("timeupdate", onTime);
    a.addEventListener("loadedmetadata", onMeta);
    a.addEventListener("play", onPlay);
    a.addEventListener("pause", onPause);
    a.addEventListener("ended", onEnded);
    return () => {
      a.pause();
      a.removeEventListener("timeupdate", onTime);
      a.removeEventListener("loadedmetadata", onMeta);
      a.removeEventListener("play", onPlay);
      a.removeEventListener("pause", onPause);
      a.removeEventListener("ended", onEnded);
      audioRef.current = null;
    };
  }, [goto]);

  const play = useCallback(
    (track: Track, queue?: Track[]) => {
      const q = queue && queue.length ? queue : [track];
      queueRef.current = q;
      const i = Math.max(0, q.findIndex((t) => t.id === track.id));
      goto(i);
    },
    [goto],
  );

  const toggle = useCallback(() => {
    const a = audioRef.current;
    if (!a || !current) return;
    if (a.paused) a.play().catch(() => {});
    else a.pause();
  }, [current]);

  const next = useCallback(() => goto(indexRef.current + 1), [goto]);
  const prev = useCallback(() => goto(indexRef.current - 1), [goto]);

  const seek = useCallback((fraction: number) => {
    const a = audioRef.current;
    if (a && a.duration) a.currentTime = fraction * a.duration;
  }, []);

  const close = useCallback(() => {
    const a = audioRef.current;
    if (a) {
      a.pause();
      a.removeAttribute("src");
      a.load();
    }
    queueRef.current = [];
    indexRef.current = -1;
    setCurrent(null);
    setIsPlaying(false);
  }, []);

  return (
    <PlayerContext.Provider
      value={{
        current,
        isPlaying,
        progress,
        duration,
        time,
        play,
        toggle,
        next,
        prev,
        seek,
        close,
        hasNext,
        hasPrev,
      }}
    >
      {children}
    </PlayerContext.Provider>
  );
}

function fmt(s: number): string {
  if (!isFinite(s) || s < 0) return "0:00";
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${sec.toString().padStart(2, "0")}`;
}

export function PlayerBar() {
  const p = usePlayer();
  if (!p.current) return null;

  const meta = [p.current.voice_name && `voice · ${p.current.voice_name}`, p.current.vocal_language]
    .filter(Boolean)
    .join("  ·  ");

  return (
    <div className="flex items-center gap-4 border-t border-border bg-surface px-5 py-3">
      <div className="flex items-center gap-2">
        <IconBtn onClick={p.prev} disabled={!p.hasPrev} label="Previous">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
            <path d="M6 6h2v12H6zm3.5 6 8.5 6V6z" />
          </svg>
        </IconBtn>
        <button
          onClick={p.toggle}
          aria-label={p.isPlaying ? "Pause" : "Play"}
          className="flex h-10 w-10 items-center justify-center rounded-full bg-accent text-white"
        >
          {p.isPlaying ? (
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
              <path d="M6 5h4v14H6zm8 0h4v14h-4z" />
            </svg>
          ) : (
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
              <path d="M8 5v14l11-7z" />
            </svg>
          )}
        </button>
        <IconBtn onClick={p.next} disabled={!p.hasNext} label="Next">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
            <path d="M16 6h2v12h-2zM6 18l8.5-6L6 6z" />
          </svg>
        </IconBtn>
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between gap-3">
          <p className="truncate text-sm font-medium">{p.current.prompt}</p>
          <span className="shrink-0 font-mono text-xs text-foreground-secondary">
            {fmt(p.time)} / {fmt(p.duration)}
          </span>
        </div>
        <input
          type="range"
          min={0}
          max={1000}
          value={Math.round(p.progress * 1000)}
          onChange={(e) => p.seek(Number(e.target.value) / 1000)}
          aria-label="Seek"
          className="mt-1.5 h-1 w-full cursor-pointer accent-accent"
        />
        {meta && <p className="mt-0.5 truncate font-mono text-[0.65rem] text-foreground-secondary">{meta}</p>}
      </div>

      <IconBtn onClick={p.close} label="Close player">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <path d="M18 6 6 18M6 6l12 12" />
        </svg>
      </IconBtn>
    </div>
  );
}

function IconBtn({
  onClick,
  disabled,
  label,
  children,
}: {
  onClick: () => void;
  disabled?: boolean;
  label: string;
  children: ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      className="flex h-8 w-8 items-center justify-center rounded-lg text-foreground-secondary transition-colors hover:bg-background hover:text-foreground disabled:cursor-not-allowed disabled:opacity-30"
    >
      {children}
    </button>
  );
}
