"use client";

import { useEffect, useState, type ReactNode } from "react";
import { getHealth } from "@/lib/engine";
import VoiceSetup from "@/components/VoiceSetup";

type View = "home" | "voice" | "library" | "settings";
type EngineState = "checking" | "online" | "offline";

const NAV: { id: View; label: string; icon: ReactNode }[] = [
  { id: "home", label: "Home", icon: <HomeIcon /> },
  { id: "voice", label: "Voice", icon: <MicIcon /> },
  { id: "library", label: "Library", icon: <LibraryIcon /> },
  { id: "settings", label: "Settings", icon: <GearIcon /> },
];

export default function AppShell() {
  const [view, setView] = useState<View>("home");
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
        <div className="mt-auto flex items-center gap-2 px-5 py-4 font-mono text-xs text-foreground-secondary">
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
        </div>
      </aside>

      <main className="flex-1 overflow-y-auto">
        {view === "home" && <HomeView engine={engine} />}
        {view === "voice" && <VoiceSetup />}
        {view === "library" && <Placeholder title="Library" phase="Phase 5" />}
        {view === "settings" && <Placeholder title="Settings" phase="Phase 4" />}
      </main>
    </div>
  );
}

function HomeView({ engine }: { engine: EngineState }) {
  return (
    <div className="mx-auto flex h-full max-w-3xl flex-col items-center justify-center px-8 text-center">
      <WaveMark large />
      <h1 className="mt-6 text-3xl font-semibold tracking-tight">Cadence</h1>
      <p className="mt-3 max-w-md text-foreground-secondary">
        Full songs from a sentence, sung in your own voice. Start by training a voice, then
        generate.
      </p>
      {engine === "offline" && (
        <p className="mt-6 rounded-xl border border-error/30 bg-error/5 px-4 py-3 text-sm text-error">
          The engine isn&apos;t running. Start it, then this will connect automatically.
        </p>
      )}
    </div>
  );
}

function Placeholder({ title, phase }: { title: string; phase: string }) {
  return (
    <div className="mx-auto flex h-full max-w-3xl flex-col items-center justify-center px-8 text-center">
      <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
      <p className="mt-2 font-mono text-sm text-foreground-secondary">Arrives in {phase}</p>
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

function HomeIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 10.5 12 3l9 7.5" />
      <path d="M5 9.5V20h14V9.5" />
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
