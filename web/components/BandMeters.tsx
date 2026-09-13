"use client";

import { INSTRUMENTS, type Bar, type Instrument } from "@/lib/audio/types";
import { PLAYER } from "@/lib/palette";

const CELLS = 16;

/**
 * Who is playing right now, and how busily. Each player keeps its own hue so
 * the band is readable without reading the labels.
 */
export function BandMeters({
  bar,
  onVolume,
  soloist,
}: {
  bar: Bar | null;
  onVolume?: (instrument: Instrument, value: number) => void;
  soloist?: Instrument | null;
}) {
  return (
    <ul className="divide-y divide-bone/10 border-y border-bone/10">
      {INSTRUMENTS.map((instrument) => {
        const { hue, name } = PLAYER[instrument];
        const count = bar?.parts[instrument]?.notes.length ?? 0;
        const playing = count > 0;
        const featured = soloist === instrument;

        return (
          <li key={instrument} className="flex items-center gap-4 py-3">
            <span
              className="w-20 shrink-0 text-[0.85rem] sm:w-24"
              style={{ color: playing ? hue : "rgba(237,230,218,0.3)" }}
            >
              {name}
              {featured && <span className="ml-1 text-bone/40">solo</span>}
            </span>

            <span
              className="flex h-2.5 flex-1 gap-[2px]"
              role="img"
              aria-label={
                playing ? `${name}, ${count} notes this bar` : `${name}, not playing this bar`
              }
            >
              {Array.from({ length: CELLS }, (_, i) => (
                <span
                  key={i}
                  className="flex-1 rounded-[1px] transition-colors duration-150"
                  style={{ background: i < count ? hue : "rgba(237,230,218,0.08)" }}
                />
              ))}
            </span>

            {onVolume && (
              <input
                type="range"
                min={0}
                max={1}
                step={0.05}
                defaultValue={0.8}
                onChange={(e) => onVolume(instrument, Number(e.target.value))}
                aria-label={`${name} volume`}
                style={{ ["--thumb" as string]: hue }}
                className="w-16 shrink-0 sm:w-24"
              />
            )}
          </li>
        );
      })}
    </ul>
  );
}
