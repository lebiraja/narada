"use client";

import { INSTRUMENTS, type Bar, type Instrument } from "@/lib/audio/types";

const LABEL: Record<Instrument, string> = {
  drums: "DRUMS",
  keys: "KEYS",
  guitar: "GUITAR",
  flute: "FLUTE",
  violin: "VIOLIN",
};

/** Note-count bars for the current bar: shows who is playing and how busily. */
export function BandMeters({
  bar,
  onVolume,
}: {
  bar: Bar | null;
  onVolume?: (instrument: Instrument, value: number) => void;
}) {
  return (
    <ul className="divide-y divide-bone/10 border-y border-bone/10">
      {INSTRUMENTS.map((instrument) => {
        const count = bar?.parts[instrument]?.notes.length ?? 0;
        const active = count > 0;
        return (
          <li key={instrument} className="flex items-center gap-4 py-3">
            <span
              className={`w-20 text-xs tracking-widest ${active ? "text-ember" : "text-bone/25"}`}
            >
              {LABEL[instrument]}
            </span>
            <span className="flex h-2 flex-1 gap-[2px]" aria-label={`${count} notes`}>
              {Array.from({ length: 16 }, (_, i) => (
                <span
                  key={i}
                  className={`flex-1 ${i < count ? "bg-ember" : "bg-bone/10"}`}
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
                aria-label={`${LABEL[instrument]} volume`}
                className="h-1 w-24 accent-ember"
              />
            )}
          </li>
        );
      })}
    </ul>
  );
}
