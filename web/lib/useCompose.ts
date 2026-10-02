"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { composeSong, socketUrl } from "./api";
import type { BandEngine } from "./audio/engine";
import type { Bar, Song } from "./audio/types";
import { ComposeMessageSchema, MALFORMED, type Plan } from "./schemas";
import { barPatches } from "./useJam";

/** Bars buffered before playback starts, so the band never outruns the writers. */
const HEAD_START = 4;

type Status = "idle" | "connecting" | "writing" | "done" | "error";

function assemble(plan: Plan, bars: Bar[]): Song {
  return {
    title: plan.title,
    key: plan.key,
    tempo: plan.tempo,
    time_signature: plan.time_signature,
    kit: plan.kit,
    patches: Object.assign({}, ...bars.map(barPatches)),
    bars,
  };
}

/**
 * Streams a composition: the header arrives first, then bars one at a time
 * into the engine's buffer. Playback starts once a few bars are ready.
 * Falls back to the blocking POST if the socket never opens.
 */
export function useCompose(
  engine: React.RefObject<BandEngine | null>,
  unlock: () => Promise<void>,
) {
  const socketRef = useRef<WebSocket | null>(null);
  const [status, setStatus] = useState<Status>("idle");
  const [plan, setPlan] = useState<Plan | null>(null);
  const [written, setWritten] = useState(0);
  const [song, setSong] = useState<Song | null>(null);
  const [error, setError] = useState<string | null>(null);

  const start = useCallback(
    async (brief: string) => {
      if (socketRef.current) return;
      await unlock();
      const current = engine.current;
      if (!current) return;

      setStatus("connecting");
      setPlan(null);
      setWritten(0);
      setSong(null);
      setError(null);

      const bars: Bar[] = [];
      let header: Plan | null = null;
      let opened = false;
      let playing = false;

      const socket = new WebSocket(socketUrl("/ws/compose"));
      socketRef.current = socket;

      socket.onopen = () => {
        opened = true;
        setStatus("writing");
        socket.send(JSON.stringify({ type: "compose", brief }));
      };

      socket.onmessage = (event) => {
        const parsed = ComposeMessageSchema.safeParse(JSON.parse(event.data));
        if (!parsed.success) {
          setError(MALFORMED);
          return;
        }
        const message = parsed.data;
        if (message.type === "plan") {
          header = message;
          setPlan(message);
          current.endAt(message.total_bars);
        } else if (message.type === "bar" && header) {
          bars.push(message.bar);
          current.buffer.push(message.bar);
          const patches = barPatches(message.bar);
          if (Object.keys(patches).length) current.applyPatches(patches);
          setWritten(bars.length);
          if (!playing && bars.length >= Math.min(HEAD_START, header.total_bars)) {
            playing = true;
            current.startLive(header.tempo, () => {}, header.time_signature);
          }
        } else if (message.type === "done" && header) {
          current.endAt(bars.length);
          setSong(assemble(header, [...bars]));
          setStatus("done");
          socket.close();
        } else if (message.type === "error") {
          setError(message.detail);
          setStatus("error");
        }
      };

      socket.onerror = async () => {
        if (opened) {
          setStatus("error");
          return;
        }
        socketRef.current = null;
        try {
          const fallback = await composeSong(brief);
          setSong(fallback);
          setStatus("done");
          await current.playSong(fallback);
        } catch (cause) {
          setError(cause instanceof Error ? cause.message : "The request did not get through.");
          setStatus("error");
        }
      };

      socket.onclose = () => {
        if (socketRef.current === socket) socketRef.current = null;
      };
    },
    [engine, unlock],
  );

  const stop = useCallback(() => {
    socketRef.current?.close();
    socketRef.current = null;
    engine.current?.stop();
    setStatus((prev) => (prev === "done" ? prev : "idle"));
  }, [engine]);

  useEffect(() => () => socketRef.current?.close(), []);

  return { status, plan, written, song, error, start, stop };
}
