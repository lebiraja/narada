import { describe, expect, it } from "vitest";

import { BarBuffer, barSeconds, LOOKAHEAD_BARS } from "./scheduler";
import type { Bar } from "./types";

const makeBar = (index: number): Bar => ({ index, chord: "Am7", parts: {} });

describe("barSeconds", () => {
  it("computes bar length from tempo", () => {
    expect(barSeconds(120)).toBeCloseTo(2);
    expect(barSeconds(60)).toBeCloseTo(4);
    expect(barSeconds(120, 3)).toBeCloseTo(1.5);
  });
});

describe("BarBuffer", () => {
  it("reports contiguous depth from the playhead", () => {
    const buffer = new BarBuffer();
    buffer.push(makeBar(4));
    buffer.push(makeBar(5));
    buffer.push(makeBar(7));

    expect(buffer.depth(4)).toBe(2);
  });

  it("asks for more while under the lookahead", () => {
    const buffer = new BarBuffer();
    for (let i = 0; i < LOOKAHEAD_BARS; i += 1) buffer.push(makeBar(i));

    expect(buffer.needsMore(0)).toBe(false);
    buffer.take(0);
    expect(buffer.needsMore(1)).toBe(true);
  });

  it("returns the requested bar and consumes it", () => {
    const buffer = new BarBuffer();
    buffer.push(makeBar(2));

    const { bar, repeated } = buffer.take(2);

    expect(bar?.index).toBe(2);
    expect(repeated).toBe(false);
    expect(buffer.depth(2)).toBe(0);
  });

  it("repeats the last played bar when the next one is late", () => {
    const buffer = new BarBuffer();
    buffer.push(makeBar(0));
    buffer.take(0);

    const { bar, repeated } = buffer.take(1);

    expect(repeated).toBe(true);
    expect(bar?.index).toBe(1);
  });

  it("returns nothing when no bar has ever played", () => {
    const buffer = new BarBuffer();

    expect(buffer.take(0)).toEqual({ bar: null, repeated: false });
  });
});
