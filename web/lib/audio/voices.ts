import * as Tone from "tone";

import { midiToNote, resolveVelocity, toSynthOptions, velToGain } from "./patch";
import type { BarPart, Instrument, Note, Patch } from "./types";
import { PIECES, voiceFor, type VoiceSpec } from "./voices.generated";

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

/** Turn a generated voice spec into Tone.PolySynth options. */
function synthOptionsFor(spec: VoiceSpec) {
  const browser = spec.browser;
  if (!browser) return undefined;
  return toSynthOptions({
    oscillator: browser.oscillator as Patch["oscillator"],
    attack: browser.attack,
    decay: browser.decay,
    sustain: browser.sustain,
    release: browser.release,
    filter_freq: browser.filter_freq,
    filter_q: 1,
    reverb: 0,
    delay: 0,
  });
}

/**
 * One instrument's playable voice.
 *
 * Each articulation gets its own synth, built lazily and kept, so a violin
 * switching between bowed and pizzicato within a bar is a different sound
 * rather than the same sound at a different velocity. A patch written by an
 * agent overrides the articulation table for that instrument.
 */
export class Voice {
  readonly instrument: Instrument;
  private gain: Tone.Gain;
  private reverb: Tone.Reverb;
  private sampler: Tone.Sampler | null = null;
  private synths = new Map<string, Tone.PolySynth>();
  private override: Tone.PolySynth | null = null;
  private useSampler = false;

  constructor(instrument: Instrument) {
    this.instrument = instrument;
    const base = voiceFor(instrument, null);
    this.reverb = new Tone.Reverb({ decay: 2.4, wet: 0.25 }).toDestination();
    this.gain = new Tone.Gain(0.8).connect(this.reverb);
    this.synths.set("", this.build(base));
  }

  private build(spec: VoiceSpec): Tone.PolySynth {
    const options = synthOptionsFor(spec);
    return new Tone.PolySynth(Tone.Synth, options).connect(this.gain);
  }

  /** The synth for one articulation, built on first use. */
  private synthFor(articulation: string | null | undefined): Tone.PolySynth {
    if (this.override) return this.override;

    const key = articulation?.trim().toLowerCase() ?? "";
    const existing = this.synths.get(key);
    if (existing) return existing;

    const synth = this.build(voiceFor(this.instrument, key));
    this.synths.set(key, synth);
    return synth;
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

  /** Swap in an agent-authored patch, overriding the articulation table. */
  applyPatch(patch: Patch): void {
    this.override?.dispose();
    this.override = new Tone.PolySynth(Tone.Synth, toSynthOptions(patch)).connect(this.gain);
    this.reverb.wet.value = patch.reverb;
    this.useSampler = false;
  }

  /** Prefer the sampler again (undo a patch). No-op if samples never loaded. */
  useSampledVoice(): void {
    this.override?.dispose();
    this.override = null;
    if (this.sampler) this.useSampler = true;
  }

  set volume(value: number) {
    this.gain.gain.rampTo(value, 0.05);
  }

  /** The pitch to sound: a named drum piece supplies its own. */
  private pitchOf(note: Note, spec: VoiceSpec): number | null {
    if (note.piece) {
      const piece = PIECES[note.piece.trim().toLowerCase().replace(/[ -]/g, "_")];
      if (!piece) return null;
      return piece.note;
    }
    if (note.pitch < 0) return null;
    return Math.max(0, Math.min(127, note.pitch + spec.transpose));
  }

  /** Schedule one bar's notes at absolute transport time `barStart` (seconds). */
  schedule(part: BarPart, barStart: number, barLength: number): void {
    for (const note of part.notes) {
      const spec = voiceFor(this.instrument, note.articulation);
      const pitch = this.pitchOf(note, spec);
      if (pitch === null) continue;

      const pieceDefault = note.piece
        ? PIECES[note.piece.trim().toLowerCase().replace(/[ -]/g, "_")]?.vel
        : undefined;
      const velocity = resolveVelocity(note.vel, pieceDefault) * spec.velocityScale;

      // An articulation that only reshapes the note keeps the sampled voice;
      // one with its own timbre needs the synth to hear the difference.
      const target: Tone.Sampler | Tone.PolySynth =
        this.useSampler && this.sampler && !spec.browser
          ? this.sampler
          : this.synthFor(note.articulation);

      target.triggerAttackRelease(
        midiToNote(pitch),
        Math.max(0.02, note.dur * spec.durationScale * barLength),
        barStart + note.start * barLength,
        velToGain(Math.min(127, velocity)),
      );
    }
  }

  dispose(): void {
    this.sampler?.dispose();
    this.override?.dispose();
    for (const synth of this.synths.values()) synth.dispose();
    this.synths.clear();
    this.gain.dispose();
    this.reverb.dispose();
  }
}
