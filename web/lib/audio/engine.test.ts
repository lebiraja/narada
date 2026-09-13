import { beforeEach, describe, expect, it, vi } from "vitest";

import { bar, part, song } from "@/lib/testing/fixtures";
import { createToneMock } from "@/lib/testing/tone-mock";

const mock = createToneMock();
vi.mock("tone", () => mock.tone);

const { BandEngine } = await import("./engine");

describe("BandEngine", () => {
  let engine: InstanceType<typeof BandEngine>;

  beforeEach(async () => {
    mock.triggered.length = 0;
    mock.repeats.length = 0;
    vi.clearAllMocks();
    engine = new BandEngine();
    await engine.init();
  });

  it("starts silent and stopped", () => {
    const states: unknown[] = [];
    engine.subscribe((state) => states.push(state));

    expect(states[0]).toMatchObject({ playing: false, bar: 0 });
  });

  it("schedules every note of a song", async () => {
    await engine.playSong(
      song([bar(0, { keys: part("keys", [60, 64]), flute: part("flute", [72]) })]),
    );

    expect(mock.triggered).toHaveLength(3);
    expect(mock.triggered.map((t) => t.note).sort()).toEqual(["C4", "C5", "E4"]);
  });

  it("places notes at the right time for the tempo", async () => {
    // 120 BPM: one bar is 2 seconds, so start 0.25 lands 0.5s in.
    await engine.playSong(song([bar(0, { keys: part("keys", [60, 64]) })]));

    const [first, second] = mock.triggered;
    expect(second.time - first.time).toBeCloseTo(0.5);
  });

  it("offsets later bars by a full bar length", async () => {
    await engine.playSong(
      song([bar(0, { keys: part("keys", [60]) }), bar(1, { keys: part("keys", [62], 1) })]),
    );

    const [first, second] = mock.triggered;
    expect(second.time - first.time).toBeCloseTo(2);
  });

  it("converts velocity to gain", async () => {
    await engine.playSong(song([bar(0, { keys: part("keys", [60]) })]));

    expect(mock.triggered[0].velocity).toBeCloseTo(90 / 127);
  });

  it("reports playing once the transport starts", async () => {
    let state = { playing: false };
    engine.subscribe((next) => (state = next));

    await engine.playSong(song([bar(0)]));

    expect(state.playing).toBe(true);
  });

  it("stops the transport and clears the buffer", async () => {
    await engine.playSong(song([bar(0, { keys: part("keys", [60]) })]));
    engine.buffer.push(bar(5));

    engine.stop();


    expect(mock.transport.stop).toHaveBeenCalled();
    expect(engine.buffer.depth(5)).toBe(0);
  });

  it("asks for bars immediately when live play starts", () => {
    const needed: number[] = [];

    engine.startLive(120, (from) => needed.push(from));

    expect(needed).toEqual([0]);
  });

  it("plays buffered bars as the transport advances", () => {
    // startLive clears the buffer, so bars arrive after the socket opens.
    engine.startLive(120, () => {});
    engine.buffer.push(bar(0, { drums: part("drums", [36]) }));

    mock.tick();

    expect(mock.triggered.map((t) => t.note)).toEqual(["C2"]);
  });

  it("asks for more bars once the buffer runs low", () => {
    const needed: number[] = [];
    engine.startLive(120, (from) => needed.push(from));
    engine.buffer.push(bar(0));

    mock.tick();

    expect(needed).toEqual([0, 1]);
  });

  it("flags starvation when a bar is late", () => {
    let state = { starved: false };
    engine.subscribe((next) => (state = next));
    engine.startLive(120, () => {});
    engine.buffer.push(bar(0, { drums: part("drums", [36]) }));

    mock.tick();
    expect(state.starved).toBe(false);

    mock.tick();
    expect(state.starved).toBe(true);
  });

  it("repeats the previous bar rather than falling silent", () => {
    engine.startLive(120, () => {});
    engine.buffer.push(bar(0, { drums: part("drums", [36]) }));

    mock.tick();
    mock.tick();

    expect(mock.triggered).toHaveLength(2);
    expect(mock.triggered[1].note).toBe("C2");
  });

  it("ramps the tempo instead of jumping", () => {
    engine.setTempo(140);

    expect(mock.transport.bpm.rampTo).toHaveBeenCalledWith(140, 0.2);
  });

  it("returns a blob when recording stops", async () => {
    await engine.startRecording();

    const blob = await engine.stopRecording();

    expect(blob).toBeInstanceOf(Blob);
  });

  it("returns nothing when stopping without recording", async () => {
    expect(await engine.stopRecording()).toBeNull();
  });

  it("stops notifying listeners after unsubscribe", async () => {
    const seen: unknown[] = [];
    const unsubscribe = engine.subscribe((state) => seen.push(state));
    const before = seen.length;

    unsubscribe();
    engine.setTempo(150);

    expect(seen).toHaveLength(before);
  });
});
