"use client";

import { useState } from "react";

import { BandMeters } from "@/components/BandMeters";
import { Chrome } from "@/components/Chrome";
import { composeSong, download, exportMidi } from "@/lib/api";
import type { Song } from "@/lib/audio/types";
import { useBand } from "@/lib/useBand";

const EXAMPLES = [
  "a rainy Chennai evening, slow 6/8, violin carries it",
  "funky 100bpm jam in A minor, flute takes the solo",
  "brooding cinematic build, drums enter late",
];

export default function ComposePage() {
  const { state, playSong, stop, setVolume } = useBand();
  const [brief, setBrief] = useState("");
  const [song, setSong] = useState<Song | null>(null);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function write() {
    if (!brief.trim() || working) return;
    setWorking(true);
    setError(null);
    try {
      const written = await composeSong(brief);
      setSong(written);
      await playSong(written);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Something went wrong.");
    } finally {
      setWorking(false);
    }
  }

  const currentBar = song?.bars[state.bar] ?? null;

  return (
    <Chrome index="01" name="COMPOSER">
      <section className="py-10">
        <label htmlFor="brief" className="text-xs uppercase tracking-[0.3em] text-bone/40">
          Brief the bandleader
        </label>
        <textarea
          id="brief"
          value={brief}
          onChange={(e) => setBrief(e.target.value)}
          rows={3}
          placeholder={EXAMPLES[0]}
          className="mt-3 w-full resize-none border border-bone/15 bg-transparent p-4 text-sm outline-none placeholder:text-bone/25 focus:border-ember"
        />
        <div className="mt-3 flex flex-wrap gap-2">
          {EXAMPLES.map((example) => (
            <button
              key={example}
              type="button"
              onClick={() => setBrief(example)}
              className="border border-bone/15 px-3 py-1 text-xs text-bone/50 hover:border-ember hover:text-ember"
            >
              {example}
            </button>
          ))}
        </div>

        <button
          type="button"
          onClick={write}
          disabled={working || !brief.trim()}
          className="mt-6 bg-ember px-6 py-3 text-sm tracking-widest text-ink disabled:bg-bone/10 disabled:text-bone/30"
        >
          {working ? "THE BAND IS WRITING…" : "WRITE IT"}
        </button>

        {error && <p className="mt-4 border-l-2 border-ember pl-3 text-xs text-ember">{error}</p>}
      </section>

      {song && (
        <section className="border-t border-bone/10 py-10">
          <div className="flex flex-wrap items-baseline justify-between gap-4">
            <div>
              <h2 className="text-3xl tracking-tight">{song.title}</h2>
              <p className="mt-1 text-xs text-bone/50">
                {song.key} · {song.tempo} BPM · {song.time_signature} · {song.bars.length} bars
              </p>
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => (state.playing ? stop() : playSong(song))}
                className="border border-bone/20 px-4 py-2 text-xs tracking-widest hover:border-ember hover:text-ember"
              >
                {state.playing ? "STOP" : "PLAY"}
              </button>
              <button
                type="button"
                onClick={async () => download(await exportMidi(song), `${song.title}-stems.zip`)}
                className="border border-bone/20 px-4 py-2 text-xs tracking-widest hover:border-ember hover:text-ember"
              >
                MIDI STEMS
              </button>
            </div>
          </div>

          <p className="mt-8 text-xs text-bone/40">
            BAR {state.bar + 1}/{song.bars.length} · {currentBar?.chord ?? "—"}
          </p>
          <div className="mt-3">
            <BandMeters bar={currentBar} onVolume={setVolume} />
          </div>
        </section>
      )}
    </Chrome>
  );
}
