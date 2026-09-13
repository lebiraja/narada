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
  const { status, bars, start, stop } = useJam(engine);
  const [recording, setRecording] = useState(false);
  const [takeUrl, setTakeUrl] = useState<string | null>(null);
  const takeUrlRef = useRef<string | null>(null);

  useEffect(() => {
    takeUrlRef.current = takeUrl;
  }, [takeUrl]);

  useEffect(() => () => {
    if (takeUrlRef.current) URL.revokeObjectURL(takeUrlRef.current);
  }, []);

  const live = status === "live";
  const captured: Song | null = bars.size
    ? {
        title: "Studio Take",
        key: "—",
        tempo: state.tempo,
        time_signature: "4/4",
        patches: {},
        bars: [...bars.values()].sort((a, b) => a.index - b.index),
      }
    : null;

  async function roll() {
    await unlock();
    if (!live) start(state.tempo);
    await engine.current?.startRecording();
    setRecording(true);
  }

  async function cut() {
    const blob = await engine.current?.stopRecording();
    setRecording(false);
    stop();
    if (!blob) return;
    if (takeUrl) URL.revokeObjectURL(takeUrl);
    setTakeUrl(URL.createObjectURL(blob));
  }

  return (
    <Chrome index="03" name="STUDIO">
      <section className="flex flex-wrap items-center gap-4 py-8">
        <button
          type="button"
          onClick={recording ? cut : roll}
          className={`px-8 py-4 text-sm tracking-widest ${
            recording ? "border border-ember text-ember" : "bg-ember text-ink"
          }`}
        >
          {recording ? "◼ CUT" : "● ROLL TAPE"}
        </button>
        <p className="text-xs text-bone/40">
          {recording
            ? `recording · bar ${state.bar + 1} · ${bars.size} bars captured`
            : "the band starts playing when the tape rolls"}
        </p>
      </section>

      <section className="py-4">
        <BandMeters bar={bars.get(state.bar) ?? null} onVolume={setVolume} />
      </section>

      {(takeUrl || captured) && (
        <section className="border-t border-bone/10 py-8">
          <h2 className="text-xs uppercase tracking-[0.3em] text-bone/40">The take</h2>
          {takeUrl && (
            <>
              <audio controls src={takeUrl} className="mt-4 w-full" />
              <div className="mt-4 flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={async () => download(await (await fetch(takeUrl)).blob(), "ai-band-take.webm")}
                  className="border border-bone/20 px-4 py-2 text-xs tracking-widest hover:border-ember hover:text-ember"
                >
                  DOWNLOAD AUDIO
                </button>
                {captured && (
                  <button
                    type="button"
                    onClick={async () => download(await exportMidi(captured), "ai-band-stems.zip")}
                    className="border border-bone/20 px-4 py-2 text-xs tracking-widest hover:border-ember hover:text-ember"
                  >
                    MIDI STEMS
                  </button>
                )}
              </div>
            </>
          )}
        </section>
      )}
    </Chrome>
  );
}
