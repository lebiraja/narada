import type { Song } from "./audio/types";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
export const WS = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000";

export async function composeSong(brief: string): Promise<Song> {
  const response = await fetch(`${API}/api/compose`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ brief }),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`The band could not write that (${response.status}): ${detail}`);
  }
  return response.json();
}

export async function exportMidi(song: Song): Promise<Blob> {
  const response = await fetch(`${API}/api/export/midi`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(song),
  });
  if (!response.ok) throw new Error(`MIDI export failed (${response.status})`);
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
