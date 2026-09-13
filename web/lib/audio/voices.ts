import * as Tone from "tone";

import { midiToNote, toSynthOptions, velToGain } from "./patch";
import type { BarPart, Instrument, Patch } from "./types";

/**
 * Sampled instruments served from our own origin. Each entry maps a few
 * anchor pitches to files; Tone.Sampler pitch-shifts to fill the gaps.
 */
const SAMPLE_MAP: Record<Instrument, Record<string, string>> = {
  drums: { C2: "kick.mp3", D2: "snare.mp3", "F#2": "hat-closed.mp3", "A#2": "crash.mp3" },
  keys: { C3: "C3.mp3", C4: "C4.mp3", C5: "C5.mp3" },
  guitar: { E2: "E2.mp3", A3: "A3.mp3", E4: "E4.mp3" },
  flute: { C4: "C4.mp3", C5: "C5.mp3", C6: "C6.mp3" },
  violin: { G3: "G3.mp3", D4: "D4.mp3", A5: "A5.mp3" },
};

/** Fallback synth character per instrument, used until samples load. */
const FALLBACK: Record<Instrument, Patch> = {
  drums: { oscillator: "square", attack: 0.001, decay: 0.12, sustain: 0, release: 0.05, filter_freq: 6000, filter_q: 1, reverb: 0.1, delay: 0 },
  keys: { oscillator: "triangle", attack: 0.005, decay: 0.4, sustain: 0.3, release: 1.2, filter_freq: 9000, filter_q: 1, reverb: 0.2, delay: 0 },
  guitar: { oscillator: "sawtooth", attack: 0.004, decay: 0.3, sustain: 0.2, release: 0.6, filter_freq: 5000, filter_q: 2, reverb: 0.15, delay: 0 },
  flute: { oscillator: "sine", attack: 0.06, decay: 0.1, sustain: 0.8, release: 0.4, filter_freq: 12000, filter_q: 1, reverb: 0.35, delay: 0 },
  violin: { oscillator: "fmsine", attack: 0.09, decay: 0.2, sustain: 0.8, release: 0.7, filter_freq: 8000, filter_q: 1.5, reverb: 0.4, delay: 0 },
};

/**
 * One instrument's playable voice. Holds a sampler (preferred) and a synth
 * (agent-authored patches, and the fallback while samples are missing).
 */
export class Voice {
  readonly instrument: Instrument;
  private gain: Tone.Gain;
  private reverb: Tone.Reverb;
  private sampler: Tone.Sampler | null = null;
  private synth: Tone.PolySynth;
  private useSampler = false;

  constructor(instrument: Instrument) {
    this.instrument = instrument;
    this.reverb = new Tone.Reverb({ decay: 2.4, wet: FALLBACK[instrument].reverb }).toDestination();
    this.gain = new Tone.Gain(0.8).connect(this.reverb);
    this.synth = new Tone.PolySynth(Tone.Synth, toSynthOptions(FALLBACK[instrument])).connect(this.gain);
  }

  /** Try to load self-hosted samples. Silently keeps the synth on failure. */
  async loadSamples(): Promise<boolean> {
    try {
      const sampler = new Tone.Sampler({
        urls: SAMPLE_MAP[this.instrument],
        baseUrl: `/samples/${this.instrument}/`,
      }).connect(this.gain);
      await Tone.loaded();
      this.sampler = sampler;
      this.useSampler = true;
      return true;
    } catch {
      return false;
    }
  }

  /** Swap in an agent-authored patch. Switches this voice to synth mode. */
  applyPatch(patch: Patch): void {
    this.synth.dispose();
    this.synth = new Tone.PolySynth(Tone.Synth, toSynthOptions(patch)).connect(this.gain);
    this.reverb.wet.value = patch.reverb;
    this.useSampler = false;
  }

  /** Prefer the sampler again (undo a patch). No-op if samples never loaded. */
  useSampledVoice(): void {
    if (this.sampler) this.useSampler = true;
  }

  set volume(value: number) {
    this.gain.gain.rampTo(value, 0.05);
  }

  /** Schedule one bar's notes at absolute transport time `barStart` (seconds). */
  schedule(part: BarPart, barStart: number, barLength: number): void {
    const target: Tone.Sampler | Tone.PolySynth =
      this.useSampler && this.sampler ? this.sampler : this.synth;

    for (const note of part.notes) {
      target.triggerAttackRelease(
        midiToNote(note.pitch),
        Math.max(0.02, note.dur * barLength),
        barStart + note.start * barLength,
        velToGain(note.vel),
      );
    }
  }

  dispose(): void {
    this.sampler?.dispose();
    this.synth.dispose();
    this.gain.dispose();
    this.reverb.dispose();
  }
}
