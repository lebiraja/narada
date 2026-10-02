import * as Tone from "tone";

import { Mixer } from "./mixer";
import { parseMeter, type Meter } from "./meter";
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
 * Owns the transport clock and the six voices. Two modes share it:
 * `playSong` schedules a finished arrangement; `startLive` pulls bars from
 * a BarBuffer that the websocket fills as playback advances. Bars fire on
 * bar-aligned Transport positions, so a tempo ramp cannot drift them.
 */
export class BandEngine {
  readonly buffer = new BarBuffer();
  private voices = new Map<Instrument, Voice>();
  private mixer: Mixer | null = null;
  private listeners = new Set<Listener>();
  private loopId: number | null = null;
  private liveEnd: number | null = null;
  private meter: Meter = parseMeter("4/4");
  private recorder: Tone.Recorder | null = null;
  private state: EngineState = { playing: false, bar: 0, tempo: 96, starved: false };

  async init(): Promise<void> {
    await Tone.start();
    const mixer = new Mixer();
    this.mixer = mixer;
    for (const instrument of INSTRUMENTS) {
      const voice = new Voice(instrument, mixer.channel(instrument));
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
      if (!patch) continue;
      this.voices.get(instrument as Instrument)?.applyPatch(patch);
      this.mixer?.setSend(instrument as Instrument, patch.reverb);
    }
  }

  setVolume(instrument: Instrument, value: number): void {
    this.mixer?.setVolume(instrument, value);
  }

  private scheduleBar(bar: Bar, time: number): void {
    const tempo = Tone.getTransport().bpm.getValueAtTime(time);
    const length = barSeconds(tempo, this.meter.beatsPerBar);
    for (const part of Object.values(bar.parts)) {
      if (part) this.voices.get(part.instrument)?.schedule(part, time, length);
    }
  }

  /** Fire `onBar` at the start of every bar, counting from 0, on the Transport. */
  private startLoop(
    tempo: number,
    timeSignature: string,
    onBar: (index: number, time: number) => void,
  ): void {
    this.stop();
    this.meter = parseMeter(timeSignature);

    const transport = Tone.getTransport();
    transport.bpm.value = tempo;
    transport.timeSignature = [this.meter.numerator, this.meter.denominator];
    let next = 0;
    this.loopId = transport.scheduleRepeat(
      (time) => {
        onBar(next, time);
        next += 1;
      },
      "1m",
      0,
    );

    transport.start("+0.1");
    this.emit({ playing: true, bar: 0, tempo });
  }

  /** Play a completed arrangement from bar 0. */
  async playSong(song: Song): Promise<void> {
    this.applyPatches(song.patches);
    this.startLoop(song.tempo, song.time_signature, (index, time) => {
      const bar = song.bars[index];
      if (bar) this.scheduleBar(bar, time);
      Tone.getDraw().schedule(() => this.emit({ bar: index }), time);
    });
  }

  /**
   * Start the live loop. `onNeedBars` fires whenever the buffer drops below
   * the lookahead so the caller can request more from the backend.
   */
  startLive(
    tempo: number,
    onNeedBars: (fromBar: number) => void,
    timeSignature = "4/4",
  ): void {
    this.startLoop(tempo, timeSignature, (index, time) => {
      if (this.liveEnd !== null && index >= this.liveEnd) {
        Tone.getDraw().schedule(() => this.stop(), time);
        return;
      }
      const { bar, repeated } = this.buffer.take(index);
      if (bar) this.scheduleBar(bar, time);

      Tone.getDraw().schedule(() => {
        this.emit({ bar: index, starved: repeated || !bar });
        if (this.buffer.needsMore(index + 1)) onNeedBars(index + 1);
      }, time);
    });
    onNeedBars(0);
  }

  /** A streamed piece has `bars` bars in all: stop after the last one instead of repeating it. */
  endAt(bars: number): void {
    this.liveEnd = bars;
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
    this.liveEnd = null;
    this.emit({ playing: false, bar: 0, starved: false });
  }

  dispose(): void {
    this.stop();
    for (const voice of this.voices.values()) voice.dispose();
    this.voices.clear();
    this.mixer?.dispose();
    this.mixer = null;
    this.listeners.clear();
  }
}
