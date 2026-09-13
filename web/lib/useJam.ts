"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { WS } from "./api";
import type { BandEngine } from "./audio/engine";
import type { Bar, Instrument } from "./audio/types";

export interface Cue {
  section: string;
  chords: string[];
  energy: number;
  density: number;
  soloist: Instrument | null;
  tacet: Instrument[];
  direction: string;
}

export interface SteerMessage {
  energy?: number;
  tempo?: number;
  mood?: string;
  solo?: Instrument | null;
  drop?: Instrument[];
}

type Status = "idle" | "connecting" | "live" | "closed" | "error";

/**
 * Connects the live loop: bars arrive over the socket into the engine's
 * buffer, and the engine asks for more as the playhead advances.
 */
export function useJam(engine: React.RefObject<BandEngine | null>) {
  const socketRef = useRef<WebSocket | null>(null);
  const [status, setStatus] = useState<Status>("idle");
  const [cue, setCue] = useState<Cue | null>(null);
  const [bars, setBars] = useState<Map<number, Bar>>(new Map());
  const [error, setError] = useState<string | null>(null);

  const send = useCallback((payload: object) => {
    if (socketRef.current?.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify(payload));
    }
  }, []);

  const start = useCallback(
    (tempo: number) => {
      const current = engine.current;
      if (!current || socketRef.current) return;

      setStatus("connecting");
      const socket = new WebSocket(`${WS}/ws/jam`);
      socketRef.current = socket;

      socket.onopen = () => {
        setStatus("live");
        setError(null);
        current.startLive(tempo, (fromBar) => send({ type: "need_bars", from_bar: fromBar }));
      };

      socket.onmessage = (event) => {
        const message = JSON.parse(event.data);
        if (message.type === "bar") {
          const bar = message.bar as Bar;
          current.buffer.push(bar);
          setBars((prev) => new Map(prev).set(bar.index, bar));
          const patches = Object.fromEntries(
            Object.entries(bar.parts)
              .filter(([, part]) => part?.patch)
              .map(([instrument, part]) => [instrument, part!.patch!]),
          );
          if (Object.keys(patches).length) current.applyPatches(patches);
        } else if (message.type === "cue") {
          setCue(message.cue as Cue);
        } else if (message.type === "steered") {
          current.setTempo(message.tempo);
        } else if (message.type === "error") {
          setError(message.detail as string);
        }
      };

      socket.onerror = () => setStatus("error");
      socket.onclose = () => {
        socketRef.current = null;
        setStatus("closed");
      };
    },
    [engine, send],
  );

  const stop = useCallback(() => {
    send({ type: "stop" });
    socketRef.current?.close();
    socketRef.current = null;
    engine.current?.stop();
    setBars(new Map());
    setCue(null);
    setStatus("idle");
  }, [engine, send]);

  const steer = useCallback(
    (message: SteerMessage) => send({ type: "steer", ...message }),
    [send],
  );

  useEffect(() => () => socketRef.current?.close(), []);

  return { status, cue, bars, error, start, stop, steer };
}
