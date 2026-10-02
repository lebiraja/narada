export interface Meter {
  numerator: number;
  denominator: number;
  /** Quarter-note beats in one bar: 6/8 is 3, 7/8 is 3.5. */
  beatsPerBar: number;
  /** Sixteenth-note steps in one bar: 4/4 is 16, 6/8 is 12. */
  stepsPerBar: number;
}

/** Parse a time signature like "6/8". Anything unreadable is 4/4. */
export function parseMeter(sig: string): Meter {
  const match = /^\s*(\d+)\s*\/\s*(\d+)\s*$/.exec(sig);
  const numerator = match ? Number(match[1]) : 0;
  const denominator = match ? Number(match[2]) : 0;
  const valid = numerator > 0 && [1, 2, 4, 8, 16, 32].includes(denominator);
  if (!valid) return parseMeter("4/4");

  const beatsPerBar = (numerator * 4) / denominator;
  return { numerator, denominator, beatsPerBar, stepsPerBar: beatsPerBar * 4 };
}
