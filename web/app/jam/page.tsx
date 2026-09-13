"use client";

import { useState } from "react";

import { BandMeters } from "@/components/BandMeters";
import { Chrome } from "@/components/Chrome";
import { INSTRUMENTS, type Instrument } from "@/lib/audio/types";
import { useBand } from "@/lib/useBand";
import { useJam } from "@/lib/useJam";

export default function JamPage() {
  const { engine, state, unlock, setVolume } = useBand();
  const { status, cue, bars, error, start, stop, steer } = useJam(engine);
  const [energy, setEnergy] = useState(5);
  const [tempo, setTempo] = useState(96);
  const [mood, setMood] = useState("");
  const [solo, setSolo] = useState<Instrument | null>(null);
  const [dropped, setDropped] = useState<Instrument[]>([]);

  const live = status === "live";
  const currentBar = bars.get(state.bar) ?? null;

  async function go() {
    await unlock();
    start(tempo);
  }

  function toggleDrop(instrument: Instrument) {
    const next = dropped.includes(instrument)
      ? dropped.filter((i) => i !== instrument)
      : [...dropped, instrument];
    setDropped(next);
    steer({ drop: next });
  }

  return (
    <Chrome index="02" name="LIVE JAM">
      <section className="flex flex-wrap items-center gap-4 py-8">
        <button
          type="button"
          onClick={live ? stop : go}
          className={`px-8 py-4 text-sm tracking-widest ${
            live ? "border border-bone/20 hover:border-ember hover:text-ember" : "bg-ember text-ink"
          }`}
        >
          {live ? "END THE SET" : "COUNT THEM IN"}
        </button>
        <p className="text-xs text-bone/40">
          {status === "connecting" && "connecting…"}
          {live && `BAR ${state.bar + 1} · ${state.tempo} BPM`}
          {state.starved && live && " · holding the groove"}
          {status === "error" && "socket error — is the api up?"}
          {status === "closed" && "set ended"}
        </p>
      </section>

      {error && (
        <p className="border-l-2 border-ember pl-3 text-xs text-ember">
          the band stopped: {error}
        </p>
      )}

      {cue && (
        <section className="border-y border-bone/10 py-6">
          <p className="text-xs uppercase tracking-[0.3em] text-bone/40">
            {cue.section} · energy {cue.energy} · density {cue.density}
          </p>
          <p className="mt-3 text-2xl tracking-tight">{cue.chords.join("  ·  ")}</p>
          {cue.direction && (
            <p className="mt-2 text-sm italic text-bone/50">&ldquo;{cue.direction}&rdquo;</p>
          )}
          {cue.soloist && <p className="mt-2 text-xs text-ember">{cue.soloist} is out front</p>}
        </section>
      )}

      <section className="py-8">
        <h2 className="text-xs uppercase tracking-[0.3em] text-bone/40">The band</h2>
        <div className="mt-4">
          <BandMeters bar={currentBar} onVolume={setVolume} />
        </div>
      </section>

      <section className="grid gap-8 border-t border-bone/10 py-8 sm:grid-cols-2">
        <div>
          <label htmlFor="energy" className="text-xs uppercase tracking-[0.3em] text-bone/40">
            Energy — {energy}
          </label>
          <input
            id="energy"
            type="range"
            min={1}
            max={10}
            value={energy}
            onChange={(e) => {
              const value = Number(e.target.value);
              setEnergy(value);
              steer({ energy: value });
            }}
            className="mt-3 w-full accent-ember"
          />

          <label htmlFor="tempo" className="mt-8 block text-xs uppercase tracking-[0.3em] text-bone/40">
            Tempo — {tempo} BPM
          </label>
          <input
            id="tempo"
            type="range"
            min={50}
            max={180}
            value={tempo}
            onChange={(e) => {
              const value = Number(e.target.value);
              setTempo(value);
              steer({ tempo: value });
            }}
            className="mt-3 w-full accent-ember"
          />

          <label htmlFor="mood" className="mt-8 block text-xs uppercase tracking-[0.3em] text-bone/40">
            Say something to the band
          </label>
          <form
            className="mt-3 flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              if (mood.trim()) steer({ mood });
              setMood("");
            }}
          >
            <input
              id="mood"
              value={mood}
              onChange={(e) => setMood(e.target.value)}
              placeholder="pull it back, let the violin breathe"
              className="flex-1 border border-bone/15 bg-transparent px-3 py-2 text-xs outline-none placeholder:text-bone/25 focus:border-ember"
            />
            <button type="submit" className="border border-bone/20 px-3 text-xs hover:border-ember hover:text-ember">
              SAY
            </button>
          </form>
        </div>

        <div>
          <p className="text-xs uppercase tracking-[0.3em] text-bone/40">Hand out the solo</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {INSTRUMENTS.map((instrument) => (
              <button
                key={instrument}
                type="button"
                onClick={() => {
                  const next = solo === instrument ? null : instrument;
                  setSolo(next);
                  steer({ solo: next });
                }}
                className={`border px-3 py-1 text-xs ${
                  solo === instrument
                    ? "border-ember bg-ember text-ink"
                    : "border-bone/15 text-bone/50 hover:border-ember hover:text-ember"
                }`}
              >
                {instrument}
              </button>
            ))}
          </div>

          <p className="mt-8 text-xs uppercase tracking-[0.3em] text-bone/40">Sit them out</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {INSTRUMENTS.map((instrument) => (
              <button
                key={instrument}
                type="button"
                onClick={() => toggleDrop(instrument)}
                className={`border px-3 py-1 text-xs ${
                  dropped.includes(instrument)
                    ? "border-bone/40 text-bone/30 line-through"
                    : "border-bone/15 text-bone/50 hover:border-ember hover:text-ember"
                }`}
              >
                {instrument}
              </button>
            ))}
          </div>
        </div>
      </section>
    </Chrome>
  );
}
