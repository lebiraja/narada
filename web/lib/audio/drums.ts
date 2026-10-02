import * as Tone from "tone";

import { midiToNote } from "./patch";
import { PIECES } from "./voices.generated";

type Family =
  | "kick"
  | "tom"
  | "snare"
  | "click"
  | "clap"
  | "hat"
  | "cymbal"
  | "china"
  | "shaker"
  | "metal";

interface Hit {
  family: Family;
  /** Seconds the hit is held before release; sets how long it rings. */
  duration: number;
  /** Pitch for tuned families; membranes default to the piece's GM note. */
  note?: string;
}

/**
 * How each kit piece is synthesised. All three hats share one synth, so a
 * closed or pedal hat cuts off a ringing open one, as on a real kit.
 */
const HITS: Record<string, Hit> = {
  kick: { family: "kick", duration: 0.4 },
  kick_soft: { family: "kick", duration: 0.3 },
  snare: { family: "snare", duration: 0.16 },
  ghost_snare: { family: "snare", duration: 0.1 },
  snare_roll: { family: "snare", duration: 0.06 },
  snare_rim: { family: "click", duration: 0.03 },
  sticks: { family: "click", duration: 0.015 },
  clap: { family: "clap", duration: 0.12 },
  hat_closed: { family: "hat", duration: 0.03 },
  hat_pedal: { family: "hat", duration: 0.06 },
  hat_open: { family: "hat", duration: 0.45 },
  ride: { family: "metal", duration: 0.6, note: "A5" },
  ride_bell: { family: "metal", duration: 0.5, note: "F6" },
  cowbell: { family: "metal", duration: 0.15, note: "C#5" },
  crash: { family: "cymbal", duration: 1.6 },
  splash: { family: "cymbal", duration: 0.5 },
  china: { family: "china", duration: 1.1 },
  tambourine: { family: "shaker", duration: 0.18 },
  shaker: { family: "shaker", duration: 0.06 },
  tom_hi: { family: "tom", duration: 0.35 },
  tom_mid: { family: "tom", duration: 0.4 },
  tom_lo: { family: "tom", duration: 0.45 },
  tom_floor: { family: "tom", duration: 0.5 },
};

/** Kit piece for a bare GM note, for drum parts written as pitches. */
const BY_NOTE = new Map<number, string>();
for (const [name, piece] of Object.entries(PIECES)) {
  if (!BY_NOTE.has(piece.note)) BY_NOTE.set(piece.note, name);
}

/** A noise burst shaped by its own filter, short release so retriggers choke. */
function noise(
  type: "white" | "pink",
  filter: Tone.FilterOptions["type"],
  frequency: number,
  Q: number,
  output: Tone.ToneAudioNode,
): { synth: Tone.NoiseSynth; filter: Tone.Filter } {
  const shaping = new Tone.Filter({ type: filter, frequency, Q });
  shaping.connect(output);
  const synth = new Tone.NoiseSynth({
    noise: { type },
    envelope: { attack: 0.001, decay: 0.04, sustain: 0.35, release: 0.06 },
  }).connect(shaping);
  return { synth, filter: shaping };
}

/**
 * A synthesised drum kit, used whenever real drum samples are missing so a
 * kit piece never falls back to a pitched beep.
 */
export class DrumKit {
  private kick: Tone.MembraneSynth;
  private tom: Tone.MembraneSynth;
  private metal: Tone.MetalSynth;
  private noises: Partial<Record<Family, Tone.NoiseSynth>> = {};
  private filters: Tone.Filter[] = [];

  constructor(output: Tone.ToneAudioNode) {
    this.kick = new Tone.MembraneSynth({
      pitchDecay: 0.05,
      octaves: 6,
      envelope: { attack: 0.001, decay: 0.35, sustain: 0, release: 0.1 },
    }).connect(output);
    this.tom = new Tone.MembraneSynth({
      pitchDecay: 0.08,
      octaves: 2,
      envelope: { attack: 0.001, decay: 0.4, sustain: 0, release: 0.2 },
    }).connect(output);
    this.metal = new Tone.MetalSynth({
      harmonicity: 5.1,
      modulationIndex: 16,
      resonance: 4000,
      octaves: 1.2,
      envelope: { attack: 0.001, decay: 0.4, release: 0.3 },
    }).connect(output);

    const families: Array<[Family, "white" | "pink", Tone.FilterOptions["type"], number, number]> = [
      ["snare", "white", "bandpass", 2200, 0.7],
      ["click", "white", "bandpass", 3200, 4],
      ["clap", "pink", "bandpass", 1300, 1.2],
      ["hat", "white", "highpass", 7500, 0.7],
      ["cymbal", "white", "highpass", 4500, 0.5],
      ["china", "pink", "bandpass", 3500, 1.8],
      ["shaker", "white", "highpass", 8500, 0.7],
    ];
    for (const [family, type, filter, frequency, Q] of families) {
      const voice = noise(type, filter, frequency, Q, output);
      this.noises[family] = voice.synth;
      this.filters.push(voice.filter);
    }
  }

  /** The kit piece a note names, by piece name or bare GM pitch. */
  static pieceFor(piece: string | null | undefined, pitch: number): string | null {
    if (piece) {
      const name = piece.trim().toLowerCase().replace(/[ -]/g, "_");
      return PIECES[name] ? name : null;
    }
    return BY_NOTE.get(pitch) ?? null;
  }

  /** Strike one piece at `time`; velocity is 0..1. */
  trigger(piece: string, time: number, velocity: number): void {
    const hit = HITS[piece];
    if (!hit) return;

    if (hit.family === "kick" || hit.family === "tom") {
      const synth = hit.family === "kick" ? this.kick : this.tom;
      synth.triggerAttackRelease(midiToNote(PIECES[piece].note), hit.duration, time, velocity);
    } else if (hit.family === "metal") {
      this.metal.triggerAttackRelease(hit.note ?? "C5", hit.duration, time, velocity);
    } else {
      this.noises[hit.family]?.triggerAttackRelease(hit.duration, time, velocity);
    }
  }

  dispose(): void {
    this.kick.dispose();
    this.tom.dispose();
    this.metal.dispose();
    for (const synth of Object.values(this.noises)) synth.dispose();
    for (const filter of this.filters) filter.dispose();
  }
}
