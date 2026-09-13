"use client";

import { useEffect, useRef, useState } from "react";

import { INSTRUMENTS } from "@/lib/audio/types";
import { PLAYER } from "@/lib/palette";

const STEPS = 32;

/** Each player's characteristic rhythm, as a step pattern. */
const FIGURE: Record<string, (step: number) => boolean> = {
  drums: (s) => s % 4 === 0 || s % 8 === 6,
  keys: (s) => s % 8 === 0 || s % 8 === 3,
  guitar: (s) => s % 2 === 1,
  flute: (s) => s >= 18 && s < 28 && s % 2 === 0,
  violin: (s) => s < 14 || (s >= 24 && s < 30),
};

/**
 * The band, playing. Five lanes advance through a bar on a shared clock —
 * the page's one piece of ambient motion, and the thing the product is.
 */
export function TrackLanes({ className = "" }: { className?: string }) {
  const [step, setStep] = useState(0);
  const paused = useRef(false);

  useEffect(() => {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (reduced.matches) return;

    const id = window.setInterval(() => {
      if (!paused.current) setStep((s) => (s + 1) % STEPS);
    }, 140);

    const onVisibility = () => (paused.current = document.hidden);
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      window.clearInterval(id);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, []);

  return (
    <div className={className} aria-hidden="true">
      {INSTRUMENTS.map((instrument) => {
        const { hue, name } = PLAYER[instrument];
        return (
          <div key={instrument} className="flex items-center gap-4 py-[6px]">
            <span
              className="w-[4.5rem] shrink-0 text-[0.7rem] tracking-wide text-bone/45"
              style={{ color: `${hue}cc` }}
            >
              {name}
            </span>
            <div className="flex flex-1 gap-[3px]">
              {Array.from({ length: STEPS }, (_, i) => {
                const hit = FIGURE[instrument](i);
                const head = i === step;
                return (
                  <span
                    key={i}
                    className="h-5 flex-1 rounded-[1px] transition-[background-color,transform] duration-150"
                    style={{
                      background: hit
                        ? head
                          ? "#ede6da"
                          : hue
                        : head
                          ? "rgba(237,230,218,0.22)"
                          : "rgba(237,230,218,0.06)",
                      transform: hit && head ? "scaleY(1.35)" : "scaleY(1)",
                    }}
                  />
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
