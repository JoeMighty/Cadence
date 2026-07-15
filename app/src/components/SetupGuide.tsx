"use client";

import { useEffect, useState } from "react";
import { getHealth, getSystem, type Health, type SystemInfo } from "@/lib/engine";

const SETUP_COMMANDS = `git clone https://github.com/JoeMighty/Cadence.git
powershell -ExecutionPolicy Bypass -File Cadence\\scripts\\setup-backends.ps1`;

/** What's-missing checklist: live ✓/✗ per requirement, with the fix for each. */
export default function SetupGuide({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [health, setHealth] = useState<Health | null>(null);
  const [system, setSystem] = useState<SystemInfo | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!open) return;
    getHealth().then(setHealth).catch(() => {});
    getSystem().then(setSystem).catch(() => {});
  }, [open]);

  if (!open) return null;

  const rows: { ok: boolean | null; name: string; why: string; fix: React.ReactNode }[] = [
    {
      ok: system?.tools ? system.tools.git : null,
      name: "Git",
      why: "The setup script uses it to download the AI backends.",
      fix: (
        <ExternalLink href="https://git-scm.com/download/win">Get Git for Windows</ExternalLink>
      ),
    },
    {
      ok: system?.tools ? system.tools.uv : null,
      name: "uv",
      why: "Builds the backends' Python environments.",
      fix: (
        <ExternalLink href="https://docs.astral.sh/uv/getting-started/installation/">
          Install uv
        </ExternalLink>
      ),
    },
    {
      ok: health ? health.acestep_installed : null,
      name: "Music backend (ACE-Step)",
      why: "Generates the music. Required for everything.",
      fix: <>Run the setup script below.</>,
    },
    {
      ok: health ? health.applio_installed : null,
      name: "Voice backend (Applio + Demucs)",
      why: "Sings in your trained voice and separates stems. Instrumental works without it.",
      fix: <>Installed by the same setup script.</>,
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
      onClick={onClose}
    >
      <div
        className="max-h-[85vh] w-full max-w-xl overflow-y-auto rounded-2xl border border-border bg-background p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold tracking-tight">Finish setting up Cadence</h2>
            <p className="mt-1 text-sm text-foreground-secondary">
              Everything below runs on your machine. Green means ready.
            </p>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="rounded-lg p-1.5 text-foreground-secondary hover:bg-surface hover:text-foreground"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M18 6 6 18M6 6l12 12" />
            </svg>
          </button>
        </div>

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

        <div className="mt-4">
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
            Installs the AI backends into{" "}
            <span className="font-mono">{health?.data_root || "Music\\Cadence"}</span>. When it
            finishes, come back — this checklist updates by itself. Full walkthrough in the{" "}
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
