import type { Bar } from "./types";

/** Bars kept ahead of the playhead before we stop asking for more. */
export const LOOKAHEAD_BARS = 4;

/**
 * Ordered buffer of generated bars. The transport pulls from the front;
 * the websocket pushes to the back. Late bars never stall playback: the
 * caller falls back to repeating the previous bar.
 */
export class BarBuffer {
  private bars = new Map<number, Bar>();
  private lastPlayed: Bar | null = null;

  push(bar: Bar): void {
    this.bars.set(bar.index, bar);
  }

  /** How many future bars are ready, counting from `playhead`. */
  depth(playhead: number): number {
    let depth = 0;
    while (this.bars.has(playhead + depth)) depth += 1;
    return depth;
  }

  needsMore(playhead: number): boolean {
    return this.depth(playhead) < LOOKAHEAD_BARS;
  }

  /**
   * Take the bar at `index`, dropping everything behind it. Returns a
   * repeat of the last played bar when the requested one has not arrived.
   */
  take(index: number): { bar: Bar | null; repeated: boolean } {
    const bar = this.bars.get(index);
    if (bar) {
      this.bars.delete(index);
      this.lastPlayed = bar;
      return { bar, repeated: false };
    }
    if (this.lastPlayed) {
      return { bar: { ...this.lastPlayed, index }, repeated: true };
    }
    return { bar: null, repeated: false };
  }

  clear(): void {
    this.bars.clear();
    this.lastPlayed = null;
  }
}

/** Seconds per bar for a tempo in BPM and a beats-per-bar count. */
export function barSeconds(tempo: number, beatsPerBar = 4): number {
  return (60 / tempo) * beatsPerBar;
}
