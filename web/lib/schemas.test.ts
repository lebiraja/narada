import { describe, expect, it } from "vitest";

import { ComposeMessageSchema, JamMessageSchema, NoteSchema, SongSchema } from "@/lib/schemas";
import { bar, drumPart, part, song } from "@/lib/testing/fixtures";

describe("schemas", () => {
  it("accepts a song the backend writes", () => {
    const written = song([bar(0, { keys: part("keys", [60], 0, "staccato"), drums: drumPart(["kick"]) })]);

    const result = SongSchema.safeParse(written);

    expect(result.success).toBe(true);
  });

  it("accepts grid fields and slurs on a note", () => {
    const note = { pitch: 60, start: 0, dur: 0.5, vel: null, step: 0, len: 8, slur: true };

    expect(NoteSchema.safeParse(note).success).toBe(true);
  });

  it("rejects a part for an instrument the band does not have", () => {
    const written = song([bar(0, { keys: part("keys", [60]) })]);
    const tampered = { ...written, bars: [{ ...written.bars[0], parts: { tuba: part("keys", [60]) } }] };

    expect(SongSchema.safeParse(tampered).success).toBe(false);
  });

  it("rejects a note without a pitch", () => {
    expect(NoteSchema.safeParse({ start: 0, dur: 1, vel: 80 }).success).toBe(false);
  });

  it("reads a jam session frame with and without a meter", () => {
    expect(JamMessageSchema.safeParse({ type: "session", id: "s", tempo: 96 }).success).toBe(true);
    expect(
      JamMessageSchema.safeParse({ type: "session", id: "s", tempo: 96, time_signature: "7/8" }).success,
    ).toBe(true);
  });

  it("rejects an unknown frame type", () => {
    expect(JamMessageSchema.safeParse({ type: "applause" }).success).toBe(false);
  });

  it("reads a compose plan and rejects one missing its length", () => {
    const plan = { type: "plan", title: "T", key: "A minor", tempo: 90, time_signature: "4/4", kit: "jazz" };

    expect(ComposeMessageSchema.safeParse({ ...plan, total_bars: 8 }).success).toBe(true);
    expect(ComposeMessageSchema.safeParse(plan).success).toBe(false);
  });
});
