export const INSTRUMENTS = ["drums", "keys", "guitar", "flute", "violin"] as const;

export type Instrument = (typeof INSTRUMENTS)[number];

export interface Note {
  pitch: number;
  start: number;
  dur: number;
  /** Null means "use the instrument's or kit piece's default". */
  vel: number | null;
  /** How the note is played: "pizz", "palm_mute", "staccato"… */
  articulation?: string | null;
  /** Drums only: the kit piece struck, which supplies the pitch. */
  piece?: string | null;
  /** Play legato into the next note. */
  slur?: boolean;
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
  /** Which drum kit: standard, room, jazz, brush, orchestra. */
  kit?: string;
  patches: Partial<Record<Instrument, Patch>>;
  bars: Bar[];
}
