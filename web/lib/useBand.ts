"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { BandEngine, type EngineState } from "./audio/engine";
import type { Instrument, Song } from "./audio/types";

const IDLE: EngineState = { playing: false, bar: 0, tempo: 96, starved: false };

/** Owns one BandEngine for the lifetime of a page and mirrors its state. */
export function useBand() {
  const engineRef = useRef<BandEngine | null>(null);
  const [state, setState] = useState<EngineState>(IDLE);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const engine = new BandEngine();
    engineRef.current = engine;
    const unsubscribe = engine.subscribe(setState);

    return () => {
      unsubscribe();
      engine.dispose();
      engineRef.current = null;
    };
  }, []);

  /** Browsers require a user gesture before audio can start. */
  const unlock = useCallback(async () => {
    if (ready || !engineRef.current) return;
    await engineRef.current.init();
    setReady(true);
  }, [ready]);

  const playSong = useCallback(
    async (song: Song) => {
      await unlock();
      await engineRef.current?.playSong(song);
    },
    [unlock],
  );

  const stop = useCallback(() => engineRef.current?.stop(), []);

  const setVolume = useCallback(
    (instrument: Instrument, value: number) => engineRef.current?.setVolume(instrument, value),
    [],
  );

  return { engine: engineRef, state, ready, unlock, playSong, stop, setVolume };
}
