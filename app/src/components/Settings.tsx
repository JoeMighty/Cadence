"use client";

import { useCallback, useEffect, useState } from "react";
import {
  deleteSecret,
  getSettings,
  getSystem,
  putSecret,
  updateSettings,
  type SecretName,
  type Settings as SettingsData,
  type SystemInfo,
} from "@/lib/engine";

const KEYS: { name: SecretName; label: string; hint: string }[] = [
  { name: "claude", label: "Claude", hint: "Better multilingual lyrics" },
  { name: "suno", label: "Suno", hint: "Optional cloud music (later)" },
  { name: "elevenlabs", label: "ElevenLabs", hint: "Optional cloud voice (later)" },
];

export default function Settings() {
  const [settings, setSettings] = useState<SettingsData | null>(null);
  const [system, setSystem] = useState<SystemInfo | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [s, sys] = await Promise.all([getSettings(), getSystem()]);
      setSettings(s);
      setSystem(sys);
    } catch {
      setError("Engine offline. Start the engine, then reload.");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function setProvider(p: "ollama" | "claude") {
    try {
      setSettings(await updateSettings(p));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not update provider");
    }
  }

  return (
    <div className="mx-auto w-full max-w-3xl px-8 py-10">
      <header className="mb-8">
        <p className="font-mono text-xs uppercase tracking-widest text-foreground-secondary">
          Settings
        </p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">Providers, keys, and hardware</h1>
      </header>

      {error && (
        <div className="mb-6 rounded-xl border border-error/30 bg-error/5 px-4 py-3 text-sm text-error">
          {error}
        </div>
      )}

      {/* text provider */}
      <Section title="Text provider" subtitle="Who writes the lyrics and style">
        <div className="flex gap-2">
          <ProviderOption
            label="Ollama"
            sub={
              system?.ollama.reachable
                ? system.ollama.model_present
                  ? `${system.ollama.model} · ready`
                  : `running, ${system.ollama.model} missing`
                : "not running"
            }
            active={settings?.text_provider === "ollama"}
            ok={!!system?.ollama.reachable}
            onClick={() => setProvider("ollama")}
          />
          <ProviderOption
            label="Claude"
            sub={settings?.secrets.claude ? "key saved" : "needs API key"}
            active={settings?.text_provider === "claude"}
            ok={!!settings?.secrets.claude}
            onClick={() => setProvider("claude")}
          />
        </div>
        {settings?.text_provider === "claude" && !settings.secrets.claude && (
          <p className="mt-3 text-sm text-error">Add a Claude API key below to use this provider.</p>
        )}
      </Section>

      {/* api keys */}
      <Section title="API keys" subtitle="Stored in your OS keychain, never in plaintext">
        <div className="divide-y divide-border rounded-xl border border-border bg-surface">
          {KEYS.map((k) => (
            <KeyRow
              key={k.name}
              name={k.name}
              label={k.label}
              hint={k.hint}
              saved={!!settings?.secrets[k.name]}
              onChange={(s) => setSettings((prev) => (prev ? { ...prev, secrets: s } : prev))}
              onError={setError}
            />
          ))}
        </div>
      </Section>

      {/* hardware */}
      <Section title="Hardware" subtitle="What generation runs on">
        {system && (
          <div className="rounded-xl border border-border bg-surface p-5 font-mono text-sm">
            {system.gpu.available ? (
              <div className="grid gap-2">
                <Row label="Device" value={system.gpu.device} />
                <Row label="CUDA" value={system.gpu.cuda ? "available" : "no"} />
                <Row
                  label="VRAM"
                  value={`${system.gpu.vram_used_mb} / ${system.gpu.vram_total_mb} MB`}
                />
                <Row label="Driver" value={system.gpu.driver ?? "—"} />
              </div>
            ) : (
              <p className="text-foreground-secondary">
                No CUDA GPU detected — generation will run on CPU, slowly.
              </p>
            )}
          </div>
        )}
      </Section>

      {/* about */}
      <Section title="About" subtitle="">
        <div className="rounded-xl border border-border bg-surface p-5 text-sm">
          <p className="text-foreground-secondary">Cadence — local-first AI music, in your own voice.</p>
          <p className="mt-2">
            Built by{" "}
            <a
              href="https://github.com/JoeMighty/"
              target="_blank"
              rel="noopener noreferrer"
              className="font-medium text-accent hover:underline"
            >
              Jobin Bennykutty
            </a>
          </p>
        </div>
      </Section>
    </div>
  );
}

function KeyRow({
  name,
  label,
  hint,
  saved,
  onChange,
  onError,
}: {
  name: SecretName;
  label: string;
  hint: string;
  saved: boolean;
  onChange: (s: Record<SecretName, boolean>) => void;
  onError: (m: string) => void;
}) {
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);

  async function save() {
    if (!value.trim()) return;
    setBusy(true);
    try {
      onChange(await putSecret(name, value.trim()));
      setValue("");
    } catch (e) {
      onError(e instanceof Error ? e.message : "Could not save key");
    } finally {
      setBusy(false);
    }
  }

  async function clear() {
    setBusy(true);
    try {
      onChange(await deleteSecret(name));
    } catch (e) {
      onError(e instanceof Error ? e.message : "Could not clear key");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex items-center gap-4 px-5 py-4">
      <div className="w-32 shrink-0">
        <div className="flex items-center gap-2 font-medium">
          {label}
          {saved && <span className="h-1.5 w-1.5 rounded-full bg-success" />}
        </div>
        <div className="text-xs text-foreground-secondary">{hint}</div>
      </div>
      <input
        type="password"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && save()}
        autoComplete="off"
        placeholder={saved ? "•••••••• saved" : "Paste key to save"}
        className="h-9 flex-1 rounded-lg border border-border bg-background px-3 font-mono text-sm outline-none focus:border-accent"
      />
      <button
        onClick={save}
        disabled={busy || !value.trim()}
        className="h-9 rounded-lg bg-accent px-4 text-sm font-medium text-white disabled:opacity-40"
      >
        Save
      </button>
      {saved && (
        <button
          onClick={clear}
          disabled={busy}
          className="h-9 rounded-lg border border-border px-3 text-sm text-foreground-secondary hover:border-error hover:text-error"
        >
          Clear
        </button>
      )}
    </div>
  );
}

function ProviderOption({
  label,
  sub,
  active,
  ok,
  onClick,
}: {
  label: string;
  sub: string;
  active: boolean;
  ok: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex-1 rounded-xl border px-4 py-3 text-left transition-colors ${
        active ? "border-accent bg-accent/5" : "border-border hover:border-foreground-secondary"
      }`}
    >
      <div className="flex items-center gap-2 font-medium">
        {label}
        <span className={`h-1.5 w-1.5 rounded-full ${ok ? "bg-success" : "bg-foreground-secondary"}`} />
      </div>
      <div className="font-mono text-xs text-foreground-secondary">{sub}</div>
    </button>
  );
}

function Section({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
}) {
  return (
    <section className="mb-8">
      <h2 className="text-sm font-semibold">{title}</h2>
      {subtitle && <p className="mb-3 text-xs text-foreground-secondary">{subtitle}</p>}
      {!subtitle && <div className="mb-3" />}
      {children}
    </section>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-foreground-secondary">{label}</span>
      <span>{value}</span>
    </div>
  );
}
