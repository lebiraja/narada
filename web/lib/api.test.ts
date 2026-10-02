import { afterEach, describe, expect, it, vi } from "vitest";

import { composeSong, exportAudio } from "@/lib/api";
import { MALFORMED } from "@/lib/schemas";
import { song } from "@/lib/testing/fixtures";

function respond(body: BodyInit, status: number) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(body, { status })));
}

describe("api", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("returns the mp3 when the render succeeds", async () => {
    respond("ID3", 200);

    const blob = await exportAudio(song([]));

    expect(blob.size).toBe(3);
  });

  it("surfaces the server's reason when the piece is too long", async () => {
    respond(JSON.stringify({ detail: "Too many bars to render (max 256)" }), 413);

    await expect(exportAudio(song([]))).rejects.toThrow("Too many bars to render (max 256)");
  });

  it("falls back to the status when the renderer is down without a reason", async () => {
    respond("Service Unavailable", 503);

    await expect(exportAudio(song([]))).rejects.toThrow("status 503");
  });

  it("refuses a composed song that does not match the contract", async () => {
    respond(JSON.stringify({ title: "half a song" }), 200);

    await expect(composeSong("anything")).rejects.toThrow(MALFORMED);
  });
});
