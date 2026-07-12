"use client";

import { useEffect, useState, type ReactNode } from "react";
import { getHealth } from "@/lib/engine";
import Generate from "@/components/Generate";
import Library from "@/components/Library";
import Settings from "@/components/Settings";
import VoiceSetup from "@/components/VoiceSetup";

type View = "generate" | "voice" | "library" | "settings";
type EngineState = "checking" | "online" | "offline";

const NAV: { id: View; label: string; icon: ReactNode }[] = [
  { id: "generate", label: "Generate", icon: <WaveIcon /> },
  { id: "voice", label: "Voice", icon: <MicIcon /> },
  { id: "library", label: "Library", icon: <LibraryIcon /> },
  { id: "settings", label: "Settings", icon: <GearIcon /> },
];

export default function AppShell() {
  const [view, setView] = useState<View>("generate");
  const [engine, setEngine] = useState<EngineState>("checking");

  useEffect(() => {
    let alive = true;
    const check = () =>
      getHealth()
        .then(() => alive && setEngine("online"))
        .catch(() => alive && setEngine("offline"));
    check();
    const id = setInterval(check, 5000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  return (
    <div className="flex h-full">
      <aside className="flex w-56 flex-col border-r border-border bg-surface">
        <div className="flex items-center gap-2.5 px-5 py-5">
          <WaveMark />
          <span className="text-base font-semibold tracking-tight">Cadence</span>
        </div>
        <nav className="flex flex-col gap-0.5 px-3">
          {NAV.map((item) => (
            <button
              key={item.id}
              onClick={() => setView(item.id)}
              className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors ${
                view === item.id
                  ? "bg-accent/8 font-medium text-foreground"
                  : "text-foreground-secondary hover:bg-background hover:text-foreground"
              }`}
            >
              <span className={view === item.id ? "text-accent" : ""}>{item.icon}</span>
              {item.label}
            </button>
          ))}
        </nav>
        <div className="mt-auto flex items-center justify-between px-5 py-4">
          <span className="flex items-center gap-2 font-mono text-xs text-foreground-secondary">
            <span
              className={`h-2 w-2 rounded-full ${
                engine === "online"
                  ? "bg-success"
                  : engine === "offline"
                    ? "bg-error"
                    : "bg-foreground-secondary"
              }`}
            />
            {engine === "online" ? "Engine online" : engine === "offline" ? "Engine offline" : "Checking…"}
          </span>
          <ThemeToggle />
        </div>
      </aside>

      <main className="flex-1 overflow-y-auto">
        {view === "generate" && <Generate goToVoice={() => setView("voice")} />}
        {view === "voice" && <VoiceSetup />}
        {view === "library" && <Library goToGenerate={() => setView("generate")} />}
        {view === "settings" && <Settings />}
      </main>
    </div>
  );
}

function WaveMark({ large = false }: { large?: boolean }) {
  const size = large ? 48 : 24;
  return (
    <svg width={size} height={size} viewBox="-2 -2 36 36" className="text-accent" aria-hidden="true">
      <g stroke="currentColor" strokeWidth="3" strokeLinecap="round" fill="none">
        <line x1="18.02" y1="23.53" x2="19.26" y2="28.17" />
        <line x1="14.02" y1="21.45" x2="11.01" y2="29.72" />
        <line x1="10.27" y1="20.02" x2="5.02" y2="23.69" />
        <line x1="11.20" y1="16.00" x2="0.40" y2="16.00" />
        <line x1="10.27" y1="11.98" x2="5.02" y2="8.31" />
        <line x1="14.02" y1="10.55" x2="11.01" y2="2.28" />
        <line x1="18.02" y1="8.47" x2="19.26" y2="3.83" />
      </g>
    </svg>
  );
}

function ThemeToggle() {
  const [theme, setTheme] = useState<"light" | "dark">("light");

  useEffect(() => {
    setTheme((document.documentElement.dataset.theme as "light" | "dark") || "light");
  }, []);

  function toggle() {
    const next = theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem("cadence-theme", next);
    } catch {}
    setTheme(next);
  }

  return (
    <button
      onClick={toggle}
      aria-label="Toggle color theme"
      className="flex h-7 w-7 items-center justify-center rounded-lg text-foreground-secondary transition-colors hover:bg-background hover:text-foreground"
    >
      {theme === "dark" ? (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
          <circle cx="12" cy="12" r="4" />
          <path d="M12 2v2m0 16v2M4.9 4.9l1.4 1.4m11.4 11.4 1.4 1.4M2 12h2m16 0h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
        </svg>
      ) : (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z" />
        </svg>
      )}
    </button>
  );
}

function WaveIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 10v4M8 6v12M12 9v6M16 4v16M20 8v8" />
    </svg>
  );
}

function MicIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <rect x="9" y="3" width="6" height="11" rx="3" />
      <path d="M6 11a6 6 0 0 0 12 0M12 17v4" />
    </svg>
  );
}

function LibraryIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 18V5l12-2v13" />
      <circle cx="6" cy="18" r="3" />
      <circle cx="18" cy="16" r="3" />
    </svg>
  );
}

function GearIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1Z" />
    </svg>
  );
}
