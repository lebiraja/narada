import type { Patch } from "./types";

export interface SynthOptions {
  oscillator: { type: Patch["oscillator"] };
  envelope: { attack: number; decay: number; sustain: number; release: number };
}

/** Map an agent-authored patch onto Tone.PolySynth constructor options. */
export function toSynthOptions(patch: Patch): SynthOptions {
  return {
    oscillator: { type: patch.oscillator },
    envelope: {
      attack: patch.attack,
      decay: patch.decay,
      sustain: patch.sustain,
      release: patch.release,
    },
  };
}

/** MIDI note number to scientific pitch notation, e.g. 69 -> "A4". */
const NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];

export function midiToNote(pitch: number): string {
  const octave = Math.floor(pitch / 12) - 1;
  return `${NAMES[pitch % 12]}${octave}`;
}

/** MIDI velocity (1-127) to Tone's 0-1 gain. */
export function velToGain(vel: number): number {
  return Math.min(1, Math.max(0, vel / 127));
}

/** MIDI velocity with defaults applied, since a note may leave it unset. */
export const DEFAULT_VELOCITY = 90;

export function resolveVelocity(vel: number | null | undefined, fallback?: number): number {
  return vel ?? fallback ?? DEFAULT_VELOCITY;
}
