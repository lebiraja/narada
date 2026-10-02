"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { socketUrl } from "./api";
import type { BandEngine } from "./audio/engine";
import type { Bar, Instrument, Patch } from "./audio/types";
import { type Cue, JamMessageSchema, MALFORMED } from "./schemas";

export type { Cue };

export interface SteerMessage {
  energy?: number;
  tempo?: number;
  mood?: string;
  solo?: Instrument | null;
  drop?: Instrument[];
}

/** The sounds an agent rewrote this bar, ready for `engine.applyPatches`. */
export function barPatches(bar: Bar): Partial<Record<Instrument, Patch>> {
  return Object.fromEntries(
    Object.entries(bar.parts)
      .filter(([, part]) => part?.patch)
      .map(([instrument, part]) => [instrument, part!.patch!]),
  );
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
      const socket = new WebSocket(socketUrl("/ws/jam"));
      socketRef.current = socket;

      socket.onopen = () => {
        setStatus("live");
        setError(null);
      };

      socket.onmessage = (event) => {
        const parsed = JamMessageSchema.safeParse(JSON.parse(event.data));
        if (!parsed.success) {
          setError(MALFORMED);
          return;
        }
        const message = parsed.data;
        if (message.type === "session") {
          // The server opens with the session, so the meter is known before bar 0.
          current.startLive(
            tempo,
            (fromBar) => send({ type: "need_bars", from_bar: fromBar }),
            message.time_signature ?? "4/4",
          );
        } else if (message.type === "bar") {
          const bar = message.bar;
          current.buffer.push(bar);
          setBars((prev) => new Map(prev).set(bar.index, bar));
          const patches = barPatches(bar);
          if (Object.keys(patches).length) current.applyPatches(patches);
        } else if (message.type === "cue") {
          setCue(message.cue);
        } else if (message.type === "steered") {
          current.setTempo(message.tempo);
        } else if (message.type === "error") {
          setError(message.detail);
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
