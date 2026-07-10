"use client";

import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";

type EngineStatus = "checking" | "online" | "offline";

export default function Home() {
  const [status, setStatus] = useState<EngineStatus>("checking");

  useEffect(() => {
    let cancelled = false;

    invoke<string>("ping_engine")
      .then(() => {
        if (!cancelled) setStatus("online");
      })
      .catch(() => {
        if (!cancelled) setStatus("offline");
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="flex flex-1 flex-col items-center justify-center bg-background font-sans">
      <main className="flex flex-col items-center gap-4 text-center">
        <h1 className="text-3xl font-semibold tracking-tight text-foreground">
          Cadence
        </h1>
        <p className="text-foreground-secondary">
          Local-first AI music generation, in your own voice.
        </p>
        <StatusBadge status={status} />
      </main>
    </div>
  );
}

function StatusBadge({ status }: { status: EngineStatus }) {
  const label =
    status === "checking"
      ? "Checking engine…"
      : status === "online"
        ? "Engine online"
        : "Engine offline";

  const dotColor =
    status === "online"
      ? "bg-success"
      : status === "offline"
        ? "bg-error"
        : "bg-foreground-secondary";

  return (
    <div className="flex items-center gap-2 rounded-full border border-border bg-surface px-4 py-2 font-mono text-sm text-foreground-secondary">
      <span className={`h-2 w-2 rounded-full ${dotColor}`} />
      {label}
    </div>
  );
}
