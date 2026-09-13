export const INSTRUMENTS = ["drums", "keys", "guitar", "flute", "violin"] as const;

export type Instrument = (typeof INSTRUMENTS)[number];

export interface Note {
  pitch: number;
  start: number;
  dur: number;
  vel: number;
}

export interface Patch {
  oscillator: "sine" | "square" | "sawtooth" | "triangle" | "fmsine" | "amsine";
  attack: number;
  decay: number;
  sustain: number;
  release: number;
  filter_freq: number;
  filter_q: number;
  reverb: number;
  delay: number;
}

export interface BarPart {
  instrument: Instrument;
  bar: number;
  notes: Note[];
  patch: Patch | null;
}

export interface Bar {
  index: number;
  chord: string;
  parts: Partial<Record<Instrument, BarPart>>;
}

export interface Song {
  title: string;
  key: string;
  tempo: number;
  time_signature: string;
  patches: Partial<Record<Instrument, Patch>>;
  bars: Bar[];
}
