"use client";

import { useEffect, useState } from "react";
import {
  cancelInstall,
  getHealth,
  getInstall,
  getJob,
  getSystem,
  startInstall,
  type Health,
  type Job,
  type SystemInfo,
} from "@/lib/engine";
import InstallProgress, { INSTALL_DOWNLOAD_GB } from "@/components/InstallProgress";

const SETUP_COMMANDS = `git clone https://github.com/JoeMighty/Cadence.git
powershell -ExecutionPolicy Bypass -File Cadence\\scripts\\setup-backends.ps1`;

/** What's-missing checklist, with one button that installs whatever is. */
export default function SetupGuide({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [health, setHealth] = useState<Health | null>(null);
  const [system, setSystem] = useState<SystemInfo | null>(null);
  const [copied, setCopied] = useState(false);
  // The install being shown: running, or ended in a way worth reporting.
  const [job, setJob] = useState<Job | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);

  const jobId = job?.id;
  const running = job !== null && (job.status === "queued" || job.status === "installing");

  useEffect(() => {
    if (!open) return;
    getHealth().then(setHealth).catch(() => {});
    getSystem().then(setSystem).catch(() => {});
    // Reopened mid-install (or after one stopped)? Pick up where it is.
    getInstall()
      .then((latest) => {
        if (latest && latest.status !== "done") setJob(latest);
      })
      .catch(() => {});
  }, [open]);

  useEffect(() => {
    if (!open || !jobId || !running) return;
    const timer = setInterval(async () => {
      try {
        const next = await getJob(jobId);
        setJob(next);
        if (next.status === "done" || next.status === "error") {
          setCancelling(false);
          getHealth().then(setHealth).catch(() => {});
          getSystem().then(setSystem).catch(() => {});
        }
      } catch {
        /* the engine is busy for a moment; the next tick tries again */
      }
    }, 1000);
    return () => clearInterval(timer);
  }, [open, jobId, running]);

  if (!open) return null;

  async function install() {
    setStartError(null);
    try {
      const { job_id } = await startInstall();
      setJob(await getJob(job_id));
    } catch (e) {
      setStartError(e instanceof Error ? e.message : "Couldn't start the install");
    }
  }

  async function cancel() {
    setCancelling(true);
    try {
      await cancelInstall();
    } catch {
      setCancelling(false);
    }
  }

  function close() {
    // A finished install has nothing left to show; the checklist will say so.
    if (job?.status === "done") setJob(null);
    onClose();
  }

  const missing =
    health !== null && (!health.acestep_installed || !health.applio_installed || !health.acestep_models);

  const rows: { ok: boolean | null; name: string; why: string; fix: React.ReactNode }[] = [
    {
      ok: health ? health.acestep_installed : null,
      name: "Music backend (ACE-Step)",
      why: "Generates the music. Required for everything.",
      fix: <>Use Install now below.</>,
    },
    {
      ok: health ? health.applio_installed : null,
      name: "Voice backend (Applio + Demucs)",
      why: "Sings in your trained voice and separates stems. Instrumental works without it.",
      fix: <>Use Install now below.</>,
    },
    {
      ok: health ? health.acestep_models : null,
      name: "Music models",
      why: "About 11 GB the music backend loads. Without them your first song waits on this download.",
      fix: <>Use Install now below.</>,
    },
    {
      ok: system ? system.ollama.reachable && system.ollama.model_present : null,
      name: "Ollama (optional)",
      why: "Writes lyrics locally with no API key. A Claude key works instead.",
      fix: (
        <>
          <ExternalLink href="https://ollama.com/download">Install Ollama</ExternalLink>, then{" "}
          <code className="font-mono text-xs">ollama pull qwen3.5:9b</code>
        </>
      ),
    },
  ];

  async function copy() {
    try {
      await navigator.clipboard.writeText(SETUP_COMMANDS.replace(/\n/g, "\r\n"));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {}
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-6"
      onClick={close}
    >
      <div
        className="max-h-[85vh] w-full max-w-xl overflow-y-auto rounded-2xl border border-border bg-background p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold tracking-tight">Finish setting up Cadence</h2>
            {!job && (
              <p className="mt-1 text-sm text-foreground-secondary">
                Everything below runs on your machine. Green means ready.
              </p>
            )}
          </div>
          <button
            onClick={close}
            aria-label="Close"
            className="rounded-lg p-1.5 text-foreground-secondary hover:bg-surface hover:text-foreground"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M18 6 6 18M6 6l12 12" />
            </svg>
          </button>
        </div>

        {job ? (
          <InstallProgress
            job={job}
            cancelling={cancelling}
            onCancel={cancel}
            onRetry={install}
            onDone={close}
          />
        ) : (
          <>
            <div className="divide-y divide-border rounded-xl border border-border bg-surface">
              {rows.map((r) => (
                <div key={r.name} className="flex items-start gap-3 px-4 py-3">
                  <span
                    className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[0.65rem] font-bold ${
                      r.ok === null
                        ? "border border-border text-foreground-secondary"
                        : r.ok
                          ? "bg-success text-white"
                          : "bg-error text-white"
                    }`}
                  >
                    {r.ok === null ? "…" : r.ok ? "✓" : "✕"}
                  </span>
                  <div className="min-w-0 text-sm">
                    <p className="font-medium">{r.name}</p>
                    <p className="mt-0.5 text-foreground-secondary">{r.why}</p>
                    {r.ok === false && <p className="mt-1">{r.fix}</p>}
                  </div>
                </div>
              ))}
            </div>

            {missing && (
              <div className="mt-4 rounded-xl border border-accent/30 bg-accent/5 p-4">
                <p className="text-sm font-medium">Cadence can set the rest up for you</p>
                <p className="mt-1 text-xs leading-relaxed text-foreground-secondary">
                  Downloads up to about {INSTALL_DOWNLOAD_GB} GB into{" "}
                  <span className="font-mono">{health?.data_root || "Music\\Cadence"}</span> and needs about
                  25 GB free. Nothing else to install first.
                </p>
                <button
                  onClick={install}
                  className="mt-3 h-9 rounded-lg bg-accent px-4 text-sm font-medium text-white"
                >
                  Install now
                </button>
                {startError && <p className="mt-2 text-xs text-error">{startError}</p>}
              </div>
            )}

            <details className="mt-4">
              <summary className="cursor-pointer text-xs font-medium text-foreground-secondary hover:text-foreground">
                Prefer the command line?
              </summary>
              <div className="mt-3">
                <div className="mb-1.5 flex items-center justify-between">
                  <p className="text-sm font-medium">One-time setup (PowerShell)</p>
                  <button onClick={copy} className="font-mono text-xs text-accent hover:underline">
                    {copied ? "Copied ✓" : "Copy"}
                  </button>
                </div>
                <pre className="overflow-x-auto rounded-lg border border-border bg-surface px-3 py-2.5 font-mono text-xs leading-relaxed">
                  {SETUP_COMMANDS}
                </pre>
                <p className="mt-2 text-xs leading-relaxed text-foreground-secondary">
                  Does the same job, but needs Git and{" "}
                  <ExternalLink href="https://docs.astral.sh/uv/getting-started/installation/">uv</ExternalLink>{" "}
                  installed first. Full walkthrough in the{" "}
                  <a
                    href="https://joemighty.github.io/Cadence/setup.html"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-medium text-accent hover:underline"
                  >
                    setup guide
                  </a>
                  .
                </p>
              </div>
            </details>
          </>
        )}
      </div>
    </div>
  );
}

function ExternalLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="font-medium text-accent hover:underline"
    >
      {children}
    </a>
  );
}
