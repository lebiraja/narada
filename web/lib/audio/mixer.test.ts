import { beforeEach, describe, expect, it, vi } from "vitest";

import { createToneMock } from "@/lib/testing/tone-mock";
import { INSTRUMENTS } from "./types";

const mock = createToneMock();
vi.mock("tone", () => mock.tone);

const { Mixer } = await import("./mixer");

interface Recorded {
  options?: unknown;
  gain?: { rampTo: ReturnType<typeof vi.fn>; value: number };
}

const built = (kind: string) => (mock.created[kind] ?? []) as Recorded[];

describe("Mixer", () => {
  beforeEach(() => {
    for (const kind of Object.keys(mock.created)) delete mock.created[kind];
  });

  it("shares one reverb across a channel per instrument", () => {
    new Mixer();

    expect(built("Reverb")).toHaveLength(1);
    expect(built("Panner")).toHaveLength(INSTRUMENTS.length);
    expect(built("Compressor")).toHaveLength(1);
    expect(built("Limiter")).toHaveLength(1);
  });

  it("pans and highpasses every instrument", () => {
    new Mixer();

    const pans = built("Panner").map((p) => p.options);
    // Highpasses take a bare cutoff; the low-mid cuts take an options object.
    const highpasses = built("Filter").filter((f) => typeof f.options === "number");
    expect(pans).toEqual([0, 0, -0.25, 0.3, 0.15, -0.15]);
    expect(highpasses.map((f) => f.options)).toEqual([30, 30, 80, 90, 200, 180]);
  });

  it("keeps the bass centred, full-range and nearly dry", () => {
    new Mixer();

    const bass = INSTRUMENTS.indexOf("bass");
    const highpasses = built("Filter").filter((f) => typeof f.options === "number");
    expect(built("Panner")[bass].options).toBe(0);
    expect(highpasses[bass].options).toBe(30);
    expect(built("Filter")).toHaveLength(INSTRUMENTS.length + 2); // mud cuts: keys, guitar
  });

  it("returns a distinct input per instrument", () => {
    const mixer = new Mixer();

    const inputs = new Set(INSTRUMENTS.map((i) => mixer.channel(i)));

    expect(inputs.size).toBe(INSTRUMENTS.length);
  });

  it("ramps only the named channel's volume", () => {
    const mixer = new Mixer();
    const guitar = mixer.channel("guitar") as unknown as Recorded;
    const keys = mixer.channel("keys") as unknown as Recorded;

    mixer.setVolume("guitar", 0.3);

    expect(guitar.gain?.rampTo).toHaveBeenCalledWith(0.3, 0.05);
    expect(keys.gain?.rampTo).not.toHaveBeenCalled();
  });

  it("sets an instrument's reverb send", () => {
    const mixer = new Mixer();

    mixer.setSend("violin", 0.6);

    const ramped = built("Gain").filter((g) => g.gain?.rampTo.mock.calls.length);
    expect(ramped).toHaveLength(1);
    expect(ramped[0].gain?.value).toBe(0.35);
    expect(ramped[0].gain?.rampTo).toHaveBeenCalledWith(0.6, 0.05);
  });
});
