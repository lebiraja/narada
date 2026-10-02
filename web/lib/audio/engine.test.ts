import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Song } from "./types";
import { bar, part, song } from "@/lib/testing/fixtures";
import { createToneMock } from "@/lib/testing/tone-mock";

const mock = createToneMock();
vi.mock("tone", () => mock.tone);

const { BandEngine } = await import("./engine");

/** Play a song and fire one transport bar per bar of it, one second apart. */
async function play(engine: InstanceType<typeof BandEngine>, written: Song): Promise<void> {
  await engine.playSong(written);
  written.bars.forEach((_, i) => mock.tick(i));
}

describe("BandEngine", () => {
  let engine: InstanceType<typeof BandEngine>;

  beforeEach(async () => {
    mock.triggered.length = 0;
    mock.repeats.length = 0;
    for (const kind of Object.keys(mock.created)) delete mock.created[kind];
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
    await play(engine, 
      song([bar(0, { keys: part("keys", [60, 64]), flute: part("flute", [72]) })]),
    );

    expect(mock.triggered).toHaveLength(3);
    expect(mock.triggered.map((t) => t.note).sort()).toEqual(["C4", "C5", "E4"]);
  });

  it("places notes at the right time for the tempo", async () => {
    // 120 BPM: one bar is 2 seconds, so start 0.25 lands 0.5s in.
    await play(engine, song([bar(0, { keys: part("keys", [60, 64]) })]));

    const [first, second] = mock.triggered;
    expect(second.time - first.time).toBeCloseTo(0.5);
  });

  it("plays each bar at its own transport bar, not a seconds interval", async () => {
    await play(engine, 
      song([bar(0, { keys: part("keys", [60]) }), bar(1, { keys: part("keys", [62], 1) })]),
    );

    expect(mock.repeats[0].interval).toBe("1m");
    expect(mock.triggered.map((t) => t.time)).toEqual([0, 1]);
  });

  it.each([
    ["4/4", [4, 4], 0.5],
    ["3/4", [3, 4], 0.375],
    ["6/8", [6, 8], 0.375],
    ["7/8", [7, 8], 0.4375],
  ])("scales note offsets to a %s bar", async (sig, transportSig, offset) => {
    await play(engine, song([bar(0, { keys: part("keys", [60, 64]) })], { time_signature: sig }));

    const [first, second] = mock.triggered;
    expect(mock.transport.timeSignature).toEqual(transportSig);
    expect(second.time - first.time).toBeCloseTo(offset);
  });

  it("takes the meter for live play", () => {
    engine.startLive(120, () => {}, "7/8");
    engine.buffer.push(bar(0, { keys: part("keys", [60, 64]) }));

    mock.tick();

    const [first, second] = mock.triggered;
    expect(second.time - first.time).toBeCloseTo(0.4375);
  });

  it("converts velocity to gain", async () => {
    await play(engine, song([bar(0, { keys: part("keys", [60]) })]));

    expect(mock.triggered[0].velocity).toBeCloseTo(90 / 127);
  });

  it("reports playing once the transport starts", async () => {
    let state = { playing: false };
    engine.subscribe((next) => (state = next));

    await play(engine, song([bar(0)]));

    expect(state.playing).toBe(true);
  });

  it("stops the transport and clears the buffer", async () => {
    await play(engine, song([bar(0, { keys: part("keys", [60]) })]));
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

  it("stops after the last bar of a streamed piece instead of repeating it", () => {
    engine.startLive(120, () => {});
    engine.endAt(1);
    engine.buffer.push(bar(0, { drums: part("drums", [36]) }));

    mock.tick();
    mock.tick();

    expect(mock.triggered).toHaveLength(1);
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

  it("routes the band through one shared reverb", () => {
    expect(mock.created.Reverb).toHaveLength(1);
  });

  it("turns an agent patch's reverb into that instrument's send level", () => {
    const patch = {
      oscillator: "sine",
      attack: 0.01,
      decay: 0.1,
      sustain: 0.5,
      release: 0.2,
      filter_freq: 4000,
      filter_q: 1,
      reverb: 0.7,
      delay: 0,
    } as const;

    engine.applyPatches({ flute: patch });

    const ramped = (mock.created.Gain as Array<{ gain: { rampTo: ReturnType<typeof vi.fn> } }>)
      .filter((g) => g.gain.rampTo.mock.calls.length);
    expect(ramped).toHaveLength(1);
    expect(ramped[0].gain.rampTo).toHaveBeenCalledWith(0.7, 0.05);
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

describe("BandEngine with articulated notes", () => {
  let engine: InstanceType<typeof BandEngine>;

  beforeEach(async () => {
    mock.triggered.length = 0;
    mock.repeats.length = 0;
    for (const kind of Object.keys(mock.created)) delete mock.created[kind];
    vi.clearAllMocks();
    engine = new BandEngine();
    await engine.init();
  });

  it("plays a drum note written as a named kit piece", async () => {
    await play(engine, 
      song([
        bar(0, {
          drums: {
            instrument: "drums",
            bar: 0,
            notes: [{ pitch: -1, start: 0, dur: 0.1, vel: null, piece: "kick" }],
            patch: null,
          },
        }),
      ]),
    );

    expect(mock.triggered).toHaveLength(1);
    expect(mock.triggered[0].note).toBe("C2"); // GM 36
  });

  it("uses a kit piece's own velocity when the note gives none", async () => {
    await play(engine, 
      song([
        bar(0, {
          drums: {
            instrument: "drums",
            bar: 0,
            notes: [
              { pitch: -1, start: 0, dur: 0.1, vel: null, piece: "snare" },
              { pitch: -1, start: 0.5, dur: 0.1, vel: null, piece: "ghost_snare" },
            ],
            patch: null,
          },
        }),
      ]),
    );

    const [snare, ghost] = mock.triggered;
    expect(ghost.velocity).toBeLessThan(snare.velocity);
  });

  it("skips a drum note naming a piece that does not exist", async () => {
    await play(engine, 
      song([
        bar(0, {
          drums: {
            instrument: "drums",
            bar: 0,
            notes: [{ pitch: -1, start: 0, dur: 0.1, vel: null, piece: "gong" }],
            patch: null,
          },
        }),
      ]),
    );

    expect(mock.triggered).toHaveLength(0);
  });

  it("shortens a pizzicato note", async () => {
    const withArticulation = async (articulation: string | null) => {
      mock.triggered.length = 0;
      await play(engine, 
        song([
          bar(0, {
            violin: {
              instrument: "violin",
              bar: 0,
              notes: [{ pitch: 69, start: 0, dur: 0.5, vel: 90, articulation }],
              patch: null,
            },
          }),
        ]),
      );
      return mock.triggered[0].duration;
    };

    expect(await withArticulation("pizz")).toBeLessThan(await withArticulation(null));
  });

  it("plays the bass on its synth, down to its lowest note", async () => {
    await play(engine, 
      song([
        bar(0, {
          bass: {
            instrument: "bass",
            bar: 0,
            notes: [{ pitch: 28, start: 0, dur: 0.5, vel: 100, articulation: "slap" }],
            patch: null,
          },
        }),
      ]),
    );

    expect(mock.triggered[0].note).toBe("E1");
  });

  it("sounds guitar harmonics an octave above where they are written", async () => {
    await play(engine, 
      song([
        bar(0, {
          guitar: {
            instrument: "guitar",
            bar: 0,
            notes: [
              { pitch: 60, start: 0, dur: 0.25, vel: 90, articulation: "harmonics" },
            ],
            patch: null,
          },
        }),
      ]),
    );

    expect(mock.triggered[0].note).toBe("C5"); // written C4
  });

  it("plays an unknown articulation as the normal voice", async () => {
    await play(engine, 
      song([
        bar(0, {
          flute: {
            instrument: "flute",
            bar: 0,
            notes: [
              { pitch: 72, start: 0, dur: 0.25, vel: 90, articulation: "slap-bass" },
            ],
            patch: null,
          },
        }),
      ]),
    );

    expect(mock.triggered).toHaveLength(1);
    expect(mock.triggered[0].note).toBe("C5");
  });
});
