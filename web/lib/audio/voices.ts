import * as Tone from "tone";

import { DrumKit } from "./drums";
import { midiToNote, resolveVelocity, toSynthOptions, velToGain } from "./patch";
import type { BarPart, Instrument, Note, Patch } from "./types";
import { PIECES, VOICES, voiceFor, type VoiceSpec } from "./voices.generated";

/**
 * Sampled instruments served from our own origin. Each entry maps a few
 * anchor pitches to files; Tone.Sampler pitch-shifts to fill the gaps.
 */
const SAMPLE_MAP: Record<Instrument, Record<string, string>> = {
  drums: { C2: "kick.mp3", D2: "snare.mp3", "F#2": "hat-closed.mp3", "C#3": "crash.mp3" },
  bass: {},
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
 * Each articulation gets its own synth, built up front so nothing allocates
 * on the timing path. A violin switching between bowed and pizzicato within a bar is a different sound
 * rather than the same sound at a different velocity. A patch written by an
 * agent overrides the articulation table for that instrument.
 */
export class Voice {
  readonly instrument: Instrument;
  private output: Tone.ToneAudioNode;
  private kit: DrumKit | null;
  private sampler: Tone.Sampler | null = null;
  private base: Tone.PolySynth;
  private synths = new Map<string, Tone.PolySynth>();
  private override: Tone.PolySynth | null = null;
  private useSampler = false;

  constructor(instrument: Instrument, output: Tone.ToneAudioNode) {
    this.instrument = instrument;
    this.output = output;
    this.kit = instrument === "drums" ? new DrumKit(output) : null;
    this.base = this.build(voiceFor(instrument, null));
    for (const [articulation, spec] of Object.entries(VOICES[instrument])) {
      this.synths.set(articulation, this.build(spec));
    }
  }

  private build(spec: VoiceSpec): Tone.PolySynth {
    const options = synthOptionsFor(spec);
    return new Tone.PolySynth(Tone.Synth, options).connect(this.output);
  }

  /** The synth for one articulation; anything without its own timbre plays the default. */
  private synthFor(articulation: string | null | undefined): Tone.PolySynth {
    if (this.override) return this.override;

    const key = articulation?.trim().toLowerCase() ?? "";
    return this.synths.get(key) ?? this.base;
  }

  /** Try to load self-hosted samples. Keeps the synth on failure or when none exist. */
  async loadSamples(): Promise<boolean> {
    if (Object.keys(SAMPLE_MAP[this.instrument]).length === 0) return false;
    try {
      const sampler = new Tone.Sampler({
        urls: SAMPLE_MAP[this.instrument],
        baseUrl: `/samples/${this.instrument}/`,
      }).connect(this.output);
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
    this.override = new Tone.PolySynth(Tone.Synth, toSynthOptions(patch)).connect(this.output);
    this.useSampler = false;
  }

  /** Prefer the sampler again (undo a patch). No-op if samples never loaded. */
  useSampledVoice(): void {
    this.override?.dispose();
    this.override = null;
    if (this.sampler) this.useSampler = true;
  }

  /** The pitch to sound, after the articulation's transpose. */
  private pitchOf(note: Note, spec: VoiceSpec): number | null {
    if (note.pitch < 0) return null;
    return Math.max(0, Math.min(127, note.pitch + spec.transpose));
  }

  /** Schedule one bar's notes at absolute transport time `barStart` (seconds). */
  schedule(part: BarPart, barStart: number, barLength: number): void {
    if (this.kit) {
      this.scheduleDrums(part, barStart, barLength, this.kit);
      return;
    }
    for (const note of part.notes) {
      const spec = voiceFor(this.instrument, note.articulation);
      const pitch = this.pitchOf(note, spec);
      if (pitch === null) continue;

      const velocity = resolveVelocity(note.vel) * spec.velocityScale;

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

  /**
   * Drums play the synthesised kit, except a piece recorded as one of the
   * sample anchors: the sampler would pitch-shift a kick into a tom.
   */
  private scheduleDrums(part: BarPart, barStart: number, barLength: number, kit: DrumKit): void {
    for (const note of part.notes) {
      const piece = DrumKit.pieceFor(note.piece, note.pitch);
      if (piece === null) continue;

      const spec = voiceFor(this.instrument, note.articulation);
      const velocity = velToGain(
        Math.min(127, resolveVelocity(note.vel, PIECES[piece].vel) * spec.velocityScale),
      );
      const time = barStart + note.start * barLength;
      const name = midiToNote(PIECES[piece].note);

      if (this.useSampler && this.sampler && name in SAMPLE_MAP.drums) {
        this.sampler.triggerAttackRelease(name, Math.max(0.02, note.dur * barLength), time, velocity);
      } else {
        kit.trigger(piece, time, velocity);
      }
    }
  }

  dispose(): void {
    this.kit?.dispose();
    this.sampler?.dispose();
    this.override?.dispose();
    this.base.dispose();
    for (const synth of this.synths.values()) synth.dispose();
    this.synths.clear();
  }
}
