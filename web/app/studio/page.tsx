"use client";

import { useEffect, useRef, useState } from "react";

import { BandMeters } from "@/components/BandMeters";
import { Chrome } from "@/components/Chrome";
import { download, exportMidi } from "@/lib/api";
import type { Song } from "@/lib/audio/types";
import { useBand } from "@/lib/useBand";
import { useJam } from "@/lib/useJam";

export default function StudioPage() {
  const { engine, state, unlock, setVolume } = useBand();
  const { status, bars, error, start, stop } = useJam(engine);
  const [recording, setRecording] = useState(false);
  const [take, setTake] = useState<string | null>(null);
  const takeRef = useRef<string | null>(null);

  useEffect(() => {
    takeRef.current = take;
  }, [take]);

  useEffect(
    () => () => {
      if (takeRef.current) URL.revokeObjectURL(takeRef.current);
    },
    [],
  );

  const captured: Song | null = bars.size
    ? {
        title: "Studio take",
        key: "as played",
        tempo: state.tempo,
        time_signature: "4/4",
        patches: {},
        bars: [...bars.values()].sort((a, b) => a.index - b.index),
      }
    : null;

  async function roll() {
    await unlock();
    if (status !== "live") start(state.tempo);
    await engine.current?.startRecording();
    setRecording(true);
  }

  async function cut() {
    const blob = await engine.current?.stopRecording();
    setRecording(false);
    stop();
    if (!blob) return;
    if (take) URL.revokeObjectURL(take);
    setTake(URL.createObjectURL(blob));
  }

  return (
    <Chrome name="Record a take">
      <section className="flex flex-wrap items-center gap-5 py-8">
        <button
          type="button"
          onClick={recording ? cut : roll}
          className={
            recording
              ? "flex items-center gap-2.5 border border-[#a6402d] px-7 py-3.5 text-[0.9rem] text-[#d98b78]"
              : "bg-brass px-7 py-3.5 text-[0.9rem] font-medium text-stage hover:bg-brass/85"
          }
        >
          {recording && (
            <span className="h-2 w-2 rounded-full bg-[#a6402d] animate-pulse-ember" />
          )}
          {recording ? "Stop recording" : "Start recording"}
        </button>

        <p className="text-[0.85rem] text-bone/50" role="status">
          {recording
            ? `Bar ${state.bar + 1}, ${bars.size} bars down`
            : "The band starts playing when you hit record."}
        </p>
      </section>

      {error && (
        <p className="mb-6 border-l-2 border-[#a6402d] pl-3 text-[0.85rem] text-[#d98b78]">
          The band stopped playing: {error}
        </p>
      )}

      <section className="py-2">
        <BandMeters bar={bars.get(state.bar) ?? null} onVolume={setVolume} />
      </section>

      {take ? (
        <section className="border-t border-bone/10 py-8">
          <h2 className="font-display text-3xl tracking-tight">Your take</h2>
          <p className="mt-2 text-[0.85rem] text-bone/50">
            {captured?.bars.length ?? 0} bars at {state.tempo} bpm
          </p>
          <audio controls src={take} className="mt-5 w-full" />
          <div className="mt-4 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={async () => download(await (await fetch(take)).blob(), "ai-band-take.webm")}
              className="border border-bone/20 px-4 py-2 text-[0.85rem] hover:border-brass hover:text-brass"
            >
              Download audio
            </button>
            {captured && (
              <button
                type="button"
                onClick={async () => download(await exportMidi(captured), "ai-band-parts.zip")}
                className="border border-bone/20 px-4 py-2 text-[0.85rem] hover:border-brass hover:text-brass"
              >
                Download parts
              </button>
            )}
          </div>
          <p className="mt-4 max-w-[38rem] text-[0.8rem] leading-relaxed text-bone/40">
            The audio is the mix you heard. The parts are five separate MIDI files, one per
            player, so you can rebuild the arrangement with your own instruments.
          </p>
        </section>
      ) : (
        !recording && (
          <p className="border-t border-bone/10 py-8 text-[0.85rem] text-bone/40">
            Nothing recorded yet.
          </p>
        )
      )}
    </Chrome>
  );
}
