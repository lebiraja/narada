import * as Tone from "tone";

import { BarBuffer, barSeconds } from "./scheduler";
import { INSTRUMENTS, type Bar, type Instrument, type Patch, type Song } from "./types";
import { Voice } from "./voices";

export interface EngineState {
  playing: boolean;
  bar: number;
  tempo: number;
  starved: boolean;
}

type Listener = (state: EngineState) => void;

/**
 * Owns the transport clock and the five voices. Two modes share it:
 * `playSong` schedules a finished arrangement; `startLive` pulls bars from
 * a BarBuffer that the websocket fills as playback advances.
 */
export class BandEngine {
  readonly buffer = new BarBuffer();
  private voices = new Map<Instrument, Voice>();
  private listeners = new Set<Listener>();
  private loopId: number | null = null;
  private recorder: Tone.Recorder | null = null;
  private state: EngineState = { playing: false, bar: 0, tempo: 96, starved: false };

  async init(): Promise<void> {
    await Tone.start();
    for (const instrument of INSTRUMENTS) {
      const voice = new Voice(instrument);
      void voice.loadSamples();
      this.voices.set(instrument, voice);
    }
  }

  subscribe(listener: Listener): () => void {
    this.listeners.add(listener);
    listener(this.state);
    return () => this.listeners.delete(listener);
  }

  private emit(patch: Partial<EngineState>): void {
    this.state = { ...this.state, ...patch };
    for (const listener of this.listeners) listener(this.state);
  }

  setTempo(tempo: number): void {
    Tone.getTransport().bpm.rampTo(tempo, 0.2);
    this.emit({ tempo });
  }

  applyPatches(patches: Partial<Record<Instrument, Patch>>): void {
    for (const [instrument, patch] of Object.entries(patches)) {
      if (patch) this.voices.get(instrument as Instrument)?.applyPatch(patch);
    }
  }

  setVolume(instrument: Instrument, value: number): void {
    const voice = this.voices.get(instrument);
    if (voice) voice.volume = value;
  }

  private scheduleBar(bar: Bar, at: number): void {
    const length = barSeconds(this.state.tempo);
    for (const part of Object.values(bar.parts)) {
      if (part) this.voices.get(part.instrument)?.schedule(part, at, length);
    }
  }

  /** Play a completed arrangement from bar 0. */
  async playSong(song: Song): Promise<void> {
    this.stop();
    this.setTempo(song.tempo);
    this.applyPatches(song.patches);

    const transport = Tone.getTransport();
    const length = barSeconds(song.tempo);
    const start = Tone.now() + 0.2;

    song.bars.forEach((bar, i) => this.scheduleBar(bar, start + i * length));
    transport.scheduleRepeat((time) => {
      Tone.getDraw().schedule(() => this.emit({ bar: this.state.bar + 1 }), time);
    }, `${length}s`);

    transport.start();
    this.emit({ playing: true, bar: 0 });
  }

  /**
   * Start the live loop. `onNeedBars` fires whenever the buffer drops below
   * the lookahead so the caller can request more from the backend.
   */
  startLive(tempo: number, onNeedBars: (fromBar: number) => void): void {
    this.stop();
    this.setTempo(tempo);

    const transport = Tone.getTransport();
    const length = barSeconds(tempo);
    let next = 0;

    this.loopId = transport.scheduleRepeat((time) => {
      const { bar, repeated } = this.buffer.take(next);
      if (bar) this.scheduleBar(bar, time);

      const playing = next;
      next += 1;
      Tone.getDraw().schedule(() => {
        this.emit({ bar: playing, starved: repeated || !bar });
        if (this.buffer.needsMore(next)) onNeedBars(next);
      }, time);
    }, `${length}s`);

    transport.start();
    this.emit({ playing: true, bar: 0 });
    onNeedBars(0);
  }

  /** Begin capturing the master output. Returns nothing; stop yields the blob. */
  async startRecording(): Promise<void> {
    this.recorder = new Tone.Recorder();
    Tone.getDestination().connect(this.recorder);
    await this.recorder.start();
  }

  async stopRecording(): Promise<Blob | null> {
    if (!this.recorder) return null;
    const blob = await this.recorder.stop();
    Tone.getDestination().disconnect(this.recorder);
    this.recorder.dispose();
    this.recorder = null;
    return blob;
  }

  stop(): void {
    const transport = Tone.getTransport();
    if (this.loopId !== null) {
      transport.clear(this.loopId);
      this.loopId = null;
    }
    transport.stop();
    transport.cancel();
    this.buffer.clear();
    this.emit({ playing: false, bar: 0, starved: false });
  }

  dispose(): void {
    this.stop();
    for (const voice of this.voices.values()) voice.dispose();
    this.voices.clear();
    this.listeners.clear();
  }
}
