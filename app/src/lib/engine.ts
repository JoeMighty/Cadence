// Typed client for the local Cadence engine (FastAPI on 127.0.0.1:8000).
// The engine enables CORS, so the webview calls it directly with fetch.

const BASE = "http://127.0.0.1:8000";

export type ProfileStatus = "collecting" | "training" | "ready" | "error";

export interface VoiceProfile {
  id: string;
  name: string;
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

export async function getHealth(): Promise<{ status: string; mock: boolean }> {
  return json(await fetch(`${BASE}/health`));
}

export async function listProfiles(): Promise<VoiceProfile[]> {
  return json(await fetch(`${BASE}/voice/profiles`));
}

export async function getProfile(id: string): Promise<VoiceProfile> {
  return json(await fetch(`${BASE}/voice/profiles/${id}`));
}

export async function createProfile(name: string): Promise<VoiceProfile> {
  return json(
    await fetch(`${BASE}/voice/profiles`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
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
