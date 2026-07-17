// Typed client for the local Cadence engine (FastAPI on 127.0.0.1:8000).
// The engine enables CORS, so the webview calls it directly with fetch.

const BASE = "http://127.0.0.1:8000";

export type ProfileStatus = "collecting" | "training" | "ready" | "error";

export interface VoiceProfile {
  id: string;
  name: string;
  gender: "" | "male" | "female";
  status: ProfileStatus;
  created_at: number;
  trained_at: number | null;
  model_path: string | null;
  index_path: string | null;
  sample_rate: number;
  epochs: number | null;
  detail: string | null;
  error: string | null;
  total_seconds: number;
  unlock_seconds: number;
  can_train: boolean;
}

export interface Take {
  id: string;
  profile_id: string;
  filename: string;
  seconds: number;
  script_index: number | null;
  created_at: number;
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export interface Health {
  status: string;
  mock: boolean;
  acestep_installed: boolean;
  acestep_running: boolean;
  applio_installed: boolean;
  data_root: string;
  output_dir: string;
  acestep_dir: string;
  applio_dir: string;
}

export async function getHealth(): Promise<Health> {
  return json(await fetch(`${BASE}/health`));
}

export async function listProfiles(): Promise<VoiceProfile[]> {
  return json(await fetch(`${BASE}/voice/profiles`));
}

export async function getProfile(id: string): Promise<VoiceProfile> {
  return json(await fetch(`${BASE}/voice/profiles/${id}`));
}

export async function createProfile(
  name: string,
  gender: "" | "male" | "female" = "",
): Promise<VoiceProfile> {
  return json(
    await fetch(`${BASE}/voice/profiles`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, gender }),
    }),
  );
}

export async function deleteProfile(id: string): Promise<void> {
  await fetch(`${BASE}/voice/profiles/${id}`, { method: "DELETE" });
}

export async function uploadTake(
  id: string,
  wav: Blob,
  scriptIndex: number,
): Promise<{ take: Take; profile: VoiceProfile }> {
  return json(
    await fetch(`${BASE}/voice/profiles/${id}/takes?script_index=${scriptIndex}`, {
      method: "POST",
      headers: { "Content-Type": "audio/wav" },
      body: wav,
    }),
  );
}

export async function listTakes(id: string): Promise<Take[]> {
  return json(await fetch(`${BASE}/voice/profiles/${id}/takes`));
}

export async function deleteTake(takeId: string): Promise<void> {
  await fetch(`${BASE}/voice/takes/${takeId}`, { method: "DELETE" });
}

export async function trainVoice(id: string, epochs?: number): Promise<{ job_id: string }> {
  return json(
    await fetch(`${BASE}/voice/profiles/${id}/train`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(epochs ? { epochs } : {}),
    }),
  );
}

// ---------- compose / tracks ----------

export type JobStatus = "queued" | "generating" | "converting" | "done" | "error";

export interface Track {
  id: string;
  prompt: string;
  caption: string | null;
  lyrics: string | null;
  vocal_language: string | null;
  bpm: number | null;
  audio_path: string;
  voice_profile_id: string | null;
  voice_name: string | null;
  instrumental: number;
  created_at: number;
}

export interface Job {
  id: string;
  kind: string;
  status: JobStatus;
  detail: string;
  result: { track?: Track } | null;
  error: string | null;
}

export interface ComposeOptions {
  prompt: string;
  voice_profile_id?: string;
  instrumental?: boolean;
  duration?: number;
  lyrics?: string;
  output_dir?: string;
  save_stems?: boolean;
  vocal_gender?: "male" | "female";
}

export async function compose(opts: ComposeOptions): Promise<{ job_id: string }> {
  return json(
    await fetch(`${BASE}/compose`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(opts),
    }),
  );
}

export async function getJob(jobId: string): Promise<Job> {
  return json(await fetch(`${BASE}/status/${jobId}`));
}

export async function listTracks(): Promise<Track[]> {
  return json(await fetch(`${BASE}/tracks`));
}

export function trackAudioUrl(trackId: string): string {
  return `${BASE}/tracks/${trackId}/audio`;
}

export function trackExportUrl(trackId: string, fmt: "wav" | "mp3"): string {
  return `${BASE}/tracks/${trackId}/export?fmt=${fmt}`;
}

export async function deleteTrack(trackId: string): Promise<void> {
  await fetch(`${BASE}/tracks/${trackId}`, { method: "DELETE" });
}

// ---------- settings / secrets / system ----------

export type SecretName = "claude" | "openai" | "gemini" | "suno" | "elevenlabs";
export type TextProvider = "ollama" | "claude" | "openai" | "gemini";

export interface Settings {
  text_provider: TextProvider;
  secrets: Record<SecretName, boolean>;
}

export interface SystemInfo {
  gpu: {
    available: boolean;
    device: string;
    cuda?: boolean;
    vram_total_mb?: number;
    vram_used_mb?: number;
    driver?: string;
  };
  ollama: { reachable: boolean; model: string; model_present: boolean };
  tools?: { git: boolean; uv: boolean };
}

export async function getSettings(): Promise<Settings> {
  return json(await fetch(`${BASE}/settings`));
}

export async function updateSettings(text_provider: TextProvider): Promise<Settings> {
  return json(
    await fetch(`${BASE}/settings`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text_provider }),
    }),
  );
}

export async function getSystem(): Promise<SystemInfo> {
  return json(await fetch(`${BASE}/system`));
}

export async function putSecret(name: SecretName, value: string): Promise<Record<SecretName, boolean>> {
  return json(
    await fetch(`${BASE}/secrets/${name}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ value }),
    }),
  );
}

export async function deleteSecret(name: SecretName): Promise<Record<SecretName, boolean>> {
  return json(await fetch(`${BASE}/secrets/${name}`, { method: "DELETE" }));
}
