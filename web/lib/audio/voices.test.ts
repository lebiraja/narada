import { describe, expect, it } from "vitest";

import { PIECES, UNIVERSAL, VOICES, voiceFor } from "./voices.generated";
import { INSTRUMENTS } from "./types";

describe("the generated voice table", () => {
  it("covers every instrument", () => {
    for (const instrument of INSTRUMENTS) {
      expect(Object.keys(VOICES[instrument]).length).toBeGreaterThan(0);
    }
  });

  it("gives melodic instruments a browser voice to render", () => {
    for (const instrument of INSTRUMENTS) {
      if (instrument === "drums") continue;
      for (const spec of Object.values(VOICES[instrument])) {
        expect(spec.browser).not.toBeNull();
      }
    }
  });

  it("knows the named drum pieces", () => {
    expect(PIECES.kick.note).toBe(36);
    expect(PIECES.ghost_snare.note).toBe(PIECES.snare.note);
    expect(PIECES.ghost_snare.vel).toBeLessThan(PIECES.snare.vel);
  });
});

describe("voiceFor", () => {
  it("falls back to the instrument's default", () => {
    const fallback = voiceFor("violin", null);

    expect(fallback).toEqual(voiceFor("violin", "slap-bass"));
    expect(fallback.browser?.oscillator).toBe("fmsine");
  });

  it("returns a distinct timbre for a real articulation", () => {
    const bowed = voiceFor("violin", "sustain");
    const plucked = voiceFor("violin", "pizz");

    expect(plucked.browser?.attack).toBeLessThan(bowed.browser!.attack);
    expect(plucked.browser?.sustain).toBeLessThan(bowed.browser!.sustain);
  });

  it("shortens a plucked note", () => {
    expect(voiceFor("violin", "pizz").durationScale).toBeLessThan(1);
  });

  it("is case and whitespace insensitive", () => {
    expect(voiceFor("guitar", "  PALM_MUTE ")).toEqual(voiceFor("guitar", "palm_mute"));
  });

  it("keeps the instrument's timbre for a shaping articulation", () => {
    const normal = voiceFor("flute", null);
    const staccato = voiceFor("flute", "staccato");

    expect(staccato.browser).toEqual(normal.browser);
    expect(staccato.durationScale).toBe(UNIVERSAL.staccato.durationScale);
  });

  it("scales velocity for accents and ghosts", () => {
    expect(voiceFor("keys", "ghost").velocityScale).toBeLessThan(1);
    expect(voiceFor("keys", "accent").velocityScale).toBeGreaterThan(1);
  });

  it("transposes guitar harmonics an octave up", () => {
    expect(voiceFor("guitar", "harmonics").transpose).toBe(12);
  });

  it("leaves other articulations untransposed", () => {
    expect(voiceFor("violin", "pizz").transpose).toBe(0);
  });
});
