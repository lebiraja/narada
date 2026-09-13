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
  let started = false;

  const transport = {
    bpm: { rampTo: vi.fn(), value: 96 },
    start: vi.fn(() => {
      started = true;
    }),
    stop: vi.fn(() => {
      started = false;
    }),
    cancel: vi.fn(),
    clear: vi.fn(),
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
    Gain: class {
      gain = { rampTo: vi.fn(), value: 0.8 };
      connect = vi.fn(() => this);
      dispose = vi.fn();
    },
    Reverb: class {
      wet = { value: 0 };
      connect = vi.fn(() => this);
      toDestination = vi.fn(() => this);
      dispose = vi.fn();
    },
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

  return { tone, transport, triggered, repeats, tick, isStarted: () => started };
}
