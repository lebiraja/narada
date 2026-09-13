"use client";

import { useState } from "react";

import { BandMeters } from "@/components/BandMeters";
import { Chrome } from "@/components/Chrome";
import { AnimatedShinyText } from "@/components/ui/animated-shiny-text";
import { INSTRUMENTS, type Instrument } from "@/lib/audio/types";
import { PLAYER } from "@/lib/palette";
import { useBand } from "@/lib/useBand";
import { useJam } from "@/lib/useJam";

export default function JamPage() {
  const { engine, state, unlock, setVolume } = useBand();
  const { status, cue, bars, error, start, stop, steer } = useJam(engine);
  const [energy, setEnergy] = useState(5);
  const [tempo, setTempo] = useState(96);
  const [aside, setAside] = useState("");
  const [solo, setSolo] = useState<Instrument | null>(null);
  const [resting, setResting] = useState<Instrument[]>([]);

  const live = status === "live";
  const currentBar = bars.get(state.bar) ?? null;

  async function begin() {
    await unlock();
    start(tempo);
  }

  function toggleRest(instrument: Instrument) {
    const next = resting.includes(instrument)
      ? resting.filter((i) => i !== instrument)
      : [...resting, instrument];
    setResting(next);
    steer({ drop: next });
  }

  return (
    <Chrome name="Play live">
      <section className="flex flex-wrap items-center gap-5 py-8">
        <button
          type="button"
          onClick={live ? stop : begin}
          className={
            live
              ? "border border-bone/20 px-7 py-3.5 text-[0.9rem] hover:border-brass hover:text-brass"
              : "bg-brass px-7 py-3.5 text-[0.9rem] font-medium text-stage hover:bg-brass/85"
          }
        >
          {live ? "End the set" : "Count them in"}
        </button>

        <p className="text-[0.85rem] text-bone/50" role="status">
          {status === "connecting" && "Getting the band together…"}
          {live && (
            <>
              Bar {state.bar + 1} at {state.tempo} bpm
              {state.starved && (
                <AnimatedShinyText className="ml-3 inline">
                  holding the groove while they catch up
                </AnimatedShinyText>
              )}
            </>
          )}
          {status === "closed" && "The set ended."}
          {status === "error" && "Lost the connection to the band."}
        </p>
      </section>

      {error && (
        <p className="mb-6 border-l-2 border-[#a6402d] pl-3 text-[0.85rem] text-[#d98b78]">
          The band stopped playing: {error}
        </p>
      )}

      {cue && (
        <section className="border-y border-bone/10 py-6">
          <p className="font-display text-3xl tracking-tight">{cue.chords.join("   ")}</p>
          <p className="mt-2 text-[0.85rem] text-bone/50">
            {cue.section}, energy {cue.energy} of 10
            {cue.soloist && (
              <span style={{ color: PLAYER[cue.soloist].hue }}>
                {" "}
                — {PLAYER[cue.soloist].name} out front
              </span>
            )}
          </p>
          {cue.direction && (
            <p className="mt-3 font-display text-lg italic text-bone/70">{cue.direction}</p>
          )}
        </section>
      )}

      <section className="py-8">
        <BandMeters bar={currentBar} onVolume={setVolume} soloist={cue?.soloist ?? null} />
      </section>

      <section className="grid gap-10 border-t border-bone/10 py-8 sm:grid-cols-2">
        <div>
          <label htmlFor="energy" className="block text-[0.9rem] text-bone/70">
            Energy
            <span className="ml-2 text-bone/45">{energy} of 10</span>
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
            style={{ ["--thumb" as string]: "#c9962e" }}
            className="mt-3 w-full"
          />

          <label htmlFor="tempo" className="mt-8 block text-[0.9rem] text-bone/70">
            Tempo
            <span className="ml-2 text-bone/45">{tempo} bpm</span>
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
            style={{ ["--thumb" as string]: "#c9962e" }}
            className="mt-3 w-full"
          />

          <form
            className="mt-8"
            onSubmit={(e) => {
              e.preventDefault();
              if (aside.trim()) steer({ mood: aside });
              setAside("");
            }}
          >
            <label htmlFor="aside" className="block text-[0.9rem] text-bone/70">
              Say something to the bandleader
            </label>
            <div className="mt-3 flex gap-2">
              <input
                id="aside"
                value={aside}
                onChange={(e) => setAside(e.target.value)}
                placeholder="pull it back, let the violin breathe"
                className="flex-1 border border-bone/15 bg-riser/40 px-3 py-2 text-[0.85rem] outline-none placeholder:text-bone/25 focus:border-brass"
              />
              <button
                type="submit"
                className="border border-bone/20 px-4 text-[0.85rem] hover:border-brass hover:text-brass"
              >
                Send
              </button>
            </div>
          </form>
        </div>

        <div>
          <p className="text-[0.9rem] text-bone/70">Give someone the solo</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {INSTRUMENTS.map((instrument) => {
              const chosen = solo === instrument;
              return (
                <button
                  key={instrument}
                  type="button"
                  aria-pressed={chosen}
                  onClick={() => {
                    const next = chosen ? null : instrument;
                    setSolo(next);
                    steer({ solo: next });
                  }}
                  className="border px-3 py-1.5 text-[0.85rem] transition-colors"
                  style={{
                    borderColor: chosen ? PLAYER[instrument].hue : "rgba(237,230,218,0.15)",
                    background: chosen ? PLAYER[instrument].hue : "transparent",
                    color: chosen ? "#12100f" : "rgba(237,230,218,0.6)",
                  }}
                >
                  {PLAYER[instrument].name}
                </button>
              );
            })}
          </div>

          <p className="mt-8 text-[0.9rem] text-bone/70">Sit someone out</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {INSTRUMENTS.map((instrument) => {
              const out = resting.includes(instrument);
              return (
                <button
                  key={instrument}
                  type="button"
                  aria-pressed={out}
                  onClick={() => toggleRest(instrument)}
                  className={`border border-bone/15 px-3 py-1.5 text-[0.85rem] ${
                    out ? "text-bone/25 line-through" : "text-bone/60 hover:border-brass/60 hover:text-brass"
                  }`}
                >
                  {PLAYER[instrument].name}
                </button>
              );
            })}
          </div>
        </div>
      </section>
    </Chrome>
  );
}
