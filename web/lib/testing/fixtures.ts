import type { Bar, BarPart, Instrument, Song } from "@/lib/audio/types";

export function part(
  instrument: Instrument,
  pitches: number[],
  bar = 0,
  articulation?: string,
): BarPart {
  return {
    instrument,
    bar,
    notes: pitches.map((pitch, i) => ({
      pitch,
      start: i * 0.25,
      dur: 0.25,
      vel: 90,
      ...(articulation ? { articulation } : {}),
    })),
    patch: null,
  };
}

/** A drum part written the way an agent writes it: named pieces, no pitches. */
export function drumPart(pieces: string[], bar = 0): BarPart {
  return {
    instrument: "drums",
    bar,
    notes: pieces.map((piece, i) => ({
      pitch: -1,
      start: i * 0.25,
      dur: 0.1,
      vel: null,
      piece,
    })),
    patch: null,
  };
}

export function bar(index: number, parts: Partial<Record<Instrument, BarPart>> = {}): Bar {
  return { index, chord: "Am7", parts };
}

export function song(bars: Bar[], overrides: Partial<Song> = {}): Song {
  return {
    title: "Test Jam",
    key: "A minor",
    tempo: 120,
    time_signature: "4/4",
    patches: {},
    bars,
    ...overrides,
  };
}
