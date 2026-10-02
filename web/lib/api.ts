import type { Song } from "./audio/types";
import { MALFORMED, SongSchema } from "./schemas";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const WS = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000";
/** The backend's shared secret, when it runs with API_KEY set. */
const KEY = process.env.NEXT_PUBLIC_API_KEY ?? "";

const HEADERS: Record<string, string> = {
  "Content-Type": "application/json",
  ...(KEY ? { "X-API-Key": KEY } : {}),
};

export function socketUrl(path: string): string {
  return KEY ? `${WS}${path}?key=${encodeURIComponent(KEY)}` : `${WS}${path}`;
}

export async function composeSong(brief: string): Promise<Song> {
  const response = await fetch(`${API}/api/compose`, {
    method: "POST",
    headers: HEADERS,
    body: JSON.stringify({ brief }),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`The band could not write that (${response.status}): ${detail}`);
  }
  const parsed = SongSchema.safeParse(await response.json());
  if (!parsed.success) throw new Error(MALFORMED);
  return parsed.data;
}

export async function exportMidi(song: Song): Promise<Blob> {
  const response = await fetch(`${API}/api/export/midi`, {
    method: "POST",
    headers: HEADERS,
    body: JSON.stringify(song),
  });
  if (!response.ok) throw new Error(`MIDI export failed (${response.status})`);
  return response.blob();
}

export async function exportAudio(song: Song): Promise<Blob> {
  const response = await fetch(`${API}/api/export/audio`, {
    method: "POST",
    headers: HEADERS,
    body: JSON.stringify(song),
  });
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null);
    const detail =
      body && typeof body === "object" && "detail" in body && typeof body.detail === "string"
        ? body.detail
        : `status ${response.status}`;
    throw new Error(`Audio export failed: ${detail}`);
  }
  return response.blob();
}

export function download(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}
