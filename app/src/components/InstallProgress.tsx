"use client";

import { useEffect, useRef, useState } from "react";
import type { InstallStepState, Job } from "@/lib/engine";

/** What the install downloads, for the screen's wording (engine/app/backends.py has the real sizes). */
export const INSTALL_DOWNLOAD_GB = 20;

function elapsedLabel(seconds: number): string {
  if (seconds < 60) return `${seconds}s elapsed`;
  return `${Math.floor(seconds / 60)}m ${String(seconds % 60).padStart(2, "0")}s elapsed`;
}

/** Whole seconds since the install began; freezes once it has finished. */
function useElapsed(startedAt: number | undefined, finishedAt: number | null | undefined, running: boolean) {
  const [now, setNow] = useState(0);
  useEffect(() => {
    if (!running) return;
    const tick = () => setNow(Date.now() / 1000);
    const first = setTimeout(tick, 0);
    const id = setInterval(tick, 1000);
    return () => {
      clearTimeout(first);
      clearInterval(id);
    };
  }, [running]);
  if (!startedAt) return 0;
  const end = finishedAt ?? now;
  return end > startedAt ? Math.round(end - startedAt) : 0;
}

function StepIcon({ state }: { state: InstallStepState }) {
  if (state === "done") {
    return (
      <span className="flex h-5 w-5 items-center justify-center rounded-full bg-accent text-[0.65rem] font-bold text-white">
        ✓
      </span>
    );
  }
  if (state === "error") {
    return (
      <span className="flex h-5 w-5 items-center justify-center rounded-full bg-error text-[0.65rem] font-bold text-white">
        ✕
      </span>
    );
  }
  if (state === "running") {
    return <span className="h-5 w-5 animate-spin rounded-full border-2 border-accent border-t-transparent" />;
  }
  return <span className="h-5 w-5 rounded-full border-2 border-border" />;
}

const BAR: Record<InstallStepState, string> = {
  done: "bg-accent",
  running: "animate-pulse bg-accent/50",
  error: "bg-error",
  pending: "bg-border",
};

/** The install screen: a segmented bar of steps, what's happening now, and the full log. */
export default function InstallProgress({
  job,
  cancelling,
  onCancel,
  onRetry,
  onDone,
}: {
  job: Job;
  cancelling: boolean;
  onCancel: () => void;
  onRetry: () => void;
  onDone: () => void;
}) {
  const p = job.progress ?? null;
  const done = job.status === "done";
  const failed = job.status === "error" && !p?.cancelled;
  const cancelled = job.status === "error" && !!p?.cancelled;
  const running = !done && job.status !== "error";
  const elapsed = useElapsed(p?.started_at, p?.finished_at, running);

  const logRef = useRef<HTMLPreElement>(null);
  const logLength = p?.log.length ?? 0;
  useEffect(() => {
    const el = logRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [logLength]);

  const [copied, setCopied] = useState(false);
  async function copyDetails() {
    const text = [job.error, ...(p?.log ?? [])].filter(Boolean).join("\n");
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {}
  }

  let title = "Installing…";
  let subtitle: React.ReactNode = running ? elapsedLabel(elapsed) : null;
  if (running && !p) {
    title = "Getting ready…";
    subtitle = "Waiting for the engine to pick this up";
  } else if (done) {
    title = "Everything's installed";
    subtitle = "Cadence is ready. Your first song takes a moment longer while the music model loads.";
  } else if (failed) {
    title = "The install stopped";
    subtitle = "Nothing is lost. Try again and it picks up where it left off.";
  } else if (cancelled) {
    title = "Install cancelled";
    subtitle = "Install again and it picks up where it left off.";
  }

  return (
    <div className="flex flex-col items-center text-center" aria-live="polite">
      {running ? (
        <span className="mb-4 h-9 w-9 animate-spin rounded-full border-[3px] border-accent border-t-transparent" />
      ) : (
        <span
          className={`mb-4 flex h-9 w-9 items-center justify-center rounded-full text-base font-bold text-white ${
            done ? "bg-success" : failed ? "bg-error" : "bg-foreground-secondary"
          }`}
        >
          {done ? "✓" : failed ? "✕" : "‖"}
        </span>
      )}
      <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
      {subtitle && (
        <p
          className={`mt-1 max-w-sm text-foreground-secondary ${
            running && p ? "font-mono text-xs" : "text-sm"
          }`}
        >
          {subtitle}
        </p>
      )}

      {p && (
        <div className="mt-6 w-full rounded-2xl border border-border bg-surface p-4">
          <ol
            className="grid gap-2"
            style={{ gridTemplateColumns: `repeat(${p.steps.length}, minmax(0, 1fr))` }}
          >
            {p.steps.map((s) => (
              <li key={s.id} className="flex min-w-0 flex-col items-center gap-2">
                <div className={`h-1.5 w-full rounded-full ${BAR[s.state]}`} />
                <StepIcon state={s.state} />
                <span
                  className={`text-xs leading-tight ${
                    s.state === "pending" ? "text-foreground-secondary" : "font-medium"
                  }`}
                >
                  {s.label}
                </span>
                {s.note && (
                  <span className="-mt-1 text-[0.65rem] leading-tight text-foreground-secondary">{s.note}</span>
                )}
              </li>
            ))}
          </ol>

          {running && (
            <div className="mt-4 truncate rounded-lg border border-border bg-background px-3 py-2 text-left font-mono text-xs text-foreground-secondary">
              {p.line || job.detail}
            </div>
          )}
        </div>
      )}

      {failed && job.error && (
        <pre className="mt-4 max-h-40 w-full overflow-auto whitespace-pre-wrap rounded-xl border border-error/30 bg-error/5 px-3 py-2.5 text-left font-mono text-xs text-error">
          {job.error}
        </pre>
      )}

      <div className="mt-5 flex flex-wrap items-center justify-center gap-3">
        {running && (
          <button
            onClick={onCancel}
            disabled={cancelling}
            className="h-9 rounded-lg border border-border px-4 text-sm font-medium hover:border-accent hover:text-accent disabled:opacity-50"
          >
            {cancelling ? "Cancelling…" : "Cancel"}
          </button>
        )}
        {(failed || cancelled) && (
          <button onClick={onRetry} className="h-9 rounded-lg bg-accent px-4 text-sm font-medium text-white">
            {failed ? "Try again" : "Resume install"}
          </button>
        )}
        {failed && (
          <button
            onClick={copyDetails}
            className="h-9 rounded-lg border border-border px-4 text-sm font-medium text-foreground-secondary hover:text-foreground"
          >
            {copied ? "Copied ✓" : "Copy details"}
          </button>
        )}
        {done && (
          <button onClick={onDone} className="h-9 rounded-lg bg-accent px-4 text-sm font-medium text-white">
            Start creating
          </button>
        )}
      </div>

      {running && (
        <p className="mt-4 max-w-md text-xs leading-relaxed text-foreground-secondary">
          This downloads about {INSTALL_DOWNLOAD_GB} GB and can take 10 to 30 minutes, depending on your
          connection. You can close this window and keep using Cadence; the install carries on.
        </p>
      )}

      {p && p.log.length > 0 && (
        <details
          className="mt-4 w-full text-left"
          onToggle={(e) => {
            const el = logRef.current;
            if (e.currentTarget.open && el) el.scrollTop = el.scrollHeight;
          }}
        >
          <summary className="cursor-pointer text-center text-xs font-medium text-foreground-secondary hover:text-foreground">
            Details
          </summary>
          <pre
            ref={logRef}
            className="mt-2 max-h-56 overflow-auto whitespace-pre-wrap rounded-lg border border-border bg-background px-3 py-2.5 font-mono text-[0.7rem] leading-relaxed text-foreground-secondary"
          >
            {p.log.join("\n")}
          </pre>
        </details>
      )}
    </div>
  );
}
