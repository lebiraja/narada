import { vi } from "vitest";

/**
 * Minimal Tone.js stand-in. Records what the engine schedules so tests can
 * assert on musical behaviour without a real audio context.
 */
export interface Triggered {
  note: string;
  duration: number;
  time: number;
  velocity: number;
}

export function createToneMock() {
  const triggered: Triggered[] = [];
  const repeats: Array<{ callback: (time: number) => void; interval: string }> = [];
  const created: Record<string, object[]> = {};
  let started = false;

  /** Remember each audio node built, by Tone class name, for wiring assertions. */
  function record(kind: string, node: object): void {
    (created[kind] ??= []).push(node);
  }

  const bpm = {
    value: 96,
    rampTo: vi.fn(),
    getValueAtTime: vi.fn(() => bpm.value),
  };
  const transport = {
    bpm,
    timeSignature: 4 as number | number[],
    start: vi.fn(() => {
      started = true;
    }),
    stop: vi.fn(() => {
      started = false;
    }),
    cancel: vi.fn(),
    clear: vi.fn((id: number) => {
      repeats[id].callback = () => {};
    }),
    scheduleRepeat: vi.fn((callback: (time: number) => void, interval: string) => {
      repeats.push({ callback, interval });
      return repeats.length - 1;
    }),
  };

  class Voiceish {
    triggerAttackRelease = vi.fn(
      (note: string, duration: number, time: number, velocity: number) => {
        triggered.push({ note, duration, time, velocity });
      },
    );
    dispose = vi.fn();
    connect = vi.fn(() => this);
    toDestination = vi.fn(() => this);
  }

  /** A node that only needs to be wired up and torn down. */
  function node(kind: string) {
    return class {
      constructor(readonly options?: unknown) {
        record(kind, this);
      }
      connect = vi.fn(() => this);
      toDestination = vi.fn(() => this);
      dispose = vi.fn();
    };
  }

  const tone = {
    start: vi.fn(async () => {}),
    now: vi.fn(() => 0),
    loaded: vi.fn(async () => {}),
    getTransport: () => transport,
    getDestination: () => ({ connect: vi.fn(), disconnect: vi.fn() }),
    getDraw: () => ({
      schedule: (callback: () => void) => callback(),
    }),
    Synth: class {},
    PolySynth: Voiceish,
    Sampler: Voiceish,
    MembraneSynth: Voiceish,
    MetalSynth: Voiceish,
    NoiseSynth: class {
      constructor() {
        record("NoiseSynth", this);
      }
      triggerAttackRelease = vi.fn((duration: number, time: number, velocity: number) => {
        triggered.push({ note: "noise", duration, time, velocity });
      });
      connect = vi.fn(() => this);
      dispose = vi.fn();
    },
    Gain: class {
      gain: { rampTo: ReturnType<typeof vi.fn>; value: number };
      constructor(value = 1) {
        this.gain = { rampTo: vi.fn(), value };
        record("Gain", this);
      }
      connect = vi.fn(() => this);
      dispose = vi.fn();
    },
    Reverb: node("Reverb"),
    Filter: node("Filter"),
    Panner: node("Panner"),
    Compressor: node("Compressor"),
    Limiter: node("Limiter"),
    Recorder: class {
      start = vi.fn(async () => {});
      stop = vi.fn(async () => new Blob(["audio"], { type: "audio/webm" }));
      dispose = vi.fn();
    },
  };

  /** Advance the transport by firing every scheduled repeat once. */
  function tick(time = 0): void {
    for (const repeat of repeats) repeat.callback(time);
  }

  return { tone, transport, triggered, repeats, created, tick, isStarted: () => started };
}
