"use client";

import { useState } from "react";

import { BandMeters } from "@/components/BandMeters";
import { Chrome } from "@/components/Chrome";
import { NumberTicker } from "@/components/ui/number-ticker";
import { ShineBorder } from "@/components/ui/shine-border";
import { download, exportAudio, exportMidi } from "@/lib/api";
import { useBand } from "@/lib/useBand";
import { useCompose } from "@/lib/useCompose";

/** Short labels to tap; the full brief is what gets sent. */
const STARTERS: Array<{ label: string; brief: string }> = [
  {
    label: "Rainy and slow",
    brief: "a rainy Chennai evening, slow, the violin carries it",
  },
  {
    label: "Funky, flute solo",
    brief: "funky and loose at 100 bpm in A minor, flute takes a solo",
  },
  {
    label: "Slow build",
    brief: "something that builds — drums stay out until the last third",
  },
];

export default function ComposePage() {
  const { engine, state, unlock, playSong, stop, setVolume } = useBand();
  const compose = useCompose(engine, unlock);
  const { song, plan, written, error } = compose;
  const [brief, setBrief] = useState("");
  const [exportError, setExportError] = useState<string | null>(null);
  const working = compose.status === "connecting" || compose.status === "writing";

  async function write() {
    if (!brief.trim() || working) return;
    await compose.start(brief);
  }

  async function exportMp3() {
    if (!song) return;
    setExportError(null);
    try {
      download(await exportAudio(song), `${song.title}.mp3`);
    } catch (cause) {
      setExportError(cause instanceof Error ? cause.message : "The export did not get through.");
    }
  }

  const currentBar = song?.bars[state.bar] ?? null;

  return (
    <Chrome name="Write a piece">
      <section className="py-10">
        <label htmlFor="brief" className="block text-[0.9rem] text-bone/70">
          What should they play?
        </label>
        <div className="relative mt-3 overflow-hidden">
          {working && <ShineBorder shineColor={["#c9962e", "#a6402d"]} duration={8} />}
          <textarea
            id="brief"
            value={brief}
            onChange={(e) => setBrief(e.target.value)}
            rows={3}
            placeholder={STARTERS[0].brief}
            className="w-full resize-none border border-bone/15 bg-riser/40 p-4 text-[0.95rem] leading-relaxed outline-none placeholder:text-bone/25 focus:border-brass"
          />
        </div>

        <div className="mt-3 flex flex-wrap gap-2">
          {STARTERS.map((starter) => (
            <button
              key={starter.label}
              type="button"
              onClick={() => setBrief(starter.brief)}
              className="border border-bone/12 px-3 py-1.5 text-[0.8rem] text-bone/55 hover:border-brass/60 hover:text-brass"
            >
              {starter.label}
            </button>
          ))}
        </div>

        <button
          type="button"
          onClick={write}
          disabled={working || !brief.trim()}
          className="mt-6 bg-brass px-6 py-3 text-[0.9rem] font-medium text-stage transition-colors hover:bg-brass/85 disabled:bg-bone/10 disabled:text-bone/30"
        >
          {working ? "The band is working it out…" : "Hand it to the band"}
        </button>

        {working && (
          <div className="mt-3 flex items-center gap-4 text-[0.8rem] text-bone/45">
            <p>
              {plan
                ? `Bar ${written} of ${plan.total_bars} written — playback starts as they land.`
                : "Every bar is six musicians deciding at once; the first few take a moment."}
            </p>
            <button
              type="button"
              onClick={compose.stop}
              className="border border-bone/20 px-3 py-1 text-bone/70 hover:border-brass hover:text-brass"
            >
              Stop
            </button>
          </div>
        )}
        {(error ?? exportError) && (
          <p className="mt-4 border-l-2 border-[#a6402d] pl-3 text-[0.85rem] text-[#d98b78]">
            {error ?? exportError}
          </p>
        )}
      </section>

      {song && (
        <section className="border-t border-bone/10 py-10">
          <div className="flex flex-wrap items-end justify-between gap-6">
            <div>
              <h2 className="font-display text-4xl tracking-tight">{song.title}</h2>
              <p className="mt-2 text-[0.85rem] text-bone/55">
                {song.key}, {song.time_signature}, {song.bars.length} bars at{" "}
                <NumberTicker value={song.tempo} className="text-bone/55" /> bpm
              </p>
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => (state.playing ? stop() : playSong(song))}
                className="border border-bone/20 px-4 py-2 text-[0.85rem] hover:border-brass hover:text-brass"
              >
                {state.playing ? "Stop" : "Play"}
              </button>
              <button
                type="button"
                onClick={async () => download(await exportMidi(song), `${song.title}-parts.zip`)}
                className="border border-bone/20 px-4 py-2 text-[0.85rem] hover:border-brass hover:text-brass"
              >
                Download parts
              </button>
              <button
                type="button"
                onClick={exportMp3}
                className="border border-bone/20 px-4 py-2 text-[0.85rem] hover:border-brass hover:text-brass"
              >
                Export MP3
              </button>
            </div>
          </div>

          <p className="mt-8 text-[0.85rem] text-bone/45">
            Bar {state.bar + 1} of {song.bars.length}
            {currentBar && <span className="ml-3 text-bone/70">{currentBar.chord}</span>}
          </p>
          <div className="mt-3">
            <BandMeters bar={currentBar} onVolume={setVolume} />
          </div>
        </section>
      )}
    </Chrome>
  );
}
