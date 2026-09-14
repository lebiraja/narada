import { describe, expect, it } from "vitest";

import { DEFAULT_VELOCITY, midiToNote, resolveVelocity, toSynthOptions, velToGain } from "./patch";
import type { Patch } from "./types";

const patch: Patch = {
  oscillator: "sawtooth",
  attack: 0.01,
  decay: 0.2,
  sustain: 0.6,
  release: 1.2,
  filter_freq: 4000,
  filter_q: 2,
  reverb: 0.3,
  delay: 0,
};

describe("toSynthOptions", () => {
  it("maps a patch onto Tone synth options", () => {
    expect(toSynthOptions(patch)).toEqual({
      oscillator: { type: "sawtooth" },
      envelope: { attack: 0.01, decay: 0.2, sustain: 0.6, release: 1.2 },
    });
  });
});

describe("midiToNote", () => {
  it("converts MIDI numbers to pitch names", () => {
    expect(midiToNote(69)).toBe("A4");
    expect(midiToNote(60)).toBe("C4");
    expect(midiToNote(61)).toBe("C#4");
  });
});

describe("velToGain", () => {
  it("normalises and clamps velocity", () => {
    expect(velToGain(127)).toBe(1);
    expect(velToGain(200)).toBe(1);
    expect(velToGain(-5)).toBe(0);
  });
});

describe("resolveVelocity", () => {
  it("uses the note's own velocity when set", () => {
    expect(resolveVelocity(64)).toBe(64);
  });

  it("falls back to a kit piece's default", () => {
    expect(resolveVelocity(null, 28)).toBe(28);
  });

  it("falls back to a sensible default when nothing is given", () => {
    expect(resolveVelocity(null)).toBe(DEFAULT_VELOCITY);
    expect(resolveVelocity(undefined)).toBe(DEFAULT_VELOCITY);
  });
});
