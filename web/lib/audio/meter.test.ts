import { describe, expect, it } from "vitest";

import { parseMeter } from "./meter";

describe("parseMeter", () => {
  it.each([
    ["4/4", 4, 4, 4, 16],
    ["3/4", 3, 4, 3, 12],
    ["6/8", 6, 8, 3, 12],
    ["7/8", 7, 8, 3.5, 14],
  ])("reads %s", (sig, numerator, denominator, beatsPerBar, stepsPerBar) => {
    const meter = parseMeter(sig);

    expect(meter).toEqual({ numerator, denominator, beatsPerBar, stepsPerBar });
  });

  it("tolerates whitespace", () => {
    expect(parseMeter(" 6 / 8 ").numerator).toBe(6);
  });

  it.each(["", "waltz", "0/4", "4/0", "5/3", "4/4/4"])("falls back to 4/4 for %j", (sig) => {
    expect(parseMeter(sig)).toEqual(parseMeter("4/4"));
  });
});
