import { beforeEach, describe, expect, it, vi } from "vitest";

import { createToneMock } from "@/lib/testing/tone-mock";
import { PIECES } from "./voices.generated";

const mock = createToneMock();
vi.mock("tone", () => mock.tone);

const { DrumKit } = await import("./drums");

const output = new mock.tone.Gain() as never;

describe("DrumKit", () => {
  beforeEach(() => {
    mock.triggered.length = 0;
    for (const kind of Object.keys(mock.created)) delete mock.created[kind];
  });

  it("sounds every kit piece", () => {
    const kit = new DrumKit(output);

    for (const piece of Object.keys(PIECES)) kit.trigger(piece, 0, 0.8);

    expect(mock.triggered).toHaveLength(Object.keys(PIECES).length);
  });

  it("tunes kick and toms to their GM notes rather than pitch-shifting one sound", () => {
    const kit = new DrumKit(output);

    kit.trigger("kick", 0, 1);
    kit.trigger("tom_floor", 0, 1);
    kit.trigger("tom_hi", 0, 1);

    expect(mock.triggered.map((t) => t.note)).toEqual(["C2", "F2", "D3"]);
  });

  it("rings an open hat far longer than a closed one", () => {
    const kit = new DrumKit(output);

    kit.trigger("hat_closed", 0, 1);
    kit.trigger("hat_open", 0, 1);

    const [closed, open] = mock.triggered;
    expect(open.duration).toBeGreaterThan(closed.duration * 5);
  });

  it("plays every hat on one synth so a closed hat chokes an open one", () => {
    const kit = new DrumKit(output);
    type Noise = { triggerAttackRelease: ReturnType<typeof vi.fn> };
    const noises = mock.created.NoiseSynth as Noise[];

    kit.trigger("hat_open", 0, 1);
    kit.trigger("hat_closed", 0.1, 1);
    kit.trigger("hat_pedal", 0.2, 1);

    const used = noises.filter((n) => n.triggerAttackRelease.mock.calls.length);
    expect(used).toHaveLength(1);
    expect(used[0].triggerAttackRelease).toHaveBeenCalledTimes(3);
  });

  it("finds a piece by name or bare GM pitch", () => {
    expect(DrumKit.pieceFor("Hat-Open", -1)).toBe("hat_open");
    expect(DrumKit.pieceFor(null, 36)).toBe("kick");
    expect(DrumKit.pieceFor("gong", -1)).toBeNull();
    expect(DrumKit.pieceFor(null, 99)).toBeNull();
  });
});
