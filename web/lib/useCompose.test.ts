import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { BandEngine } from "@/lib/audio/engine";
import type { Patch } from "@/lib/audio/types";
import { FakeSocket } from "@/lib/testing/fake-socket";
import { bar, part } from "@/lib/testing/fixtures";

vi.stubGlobal("WebSocket", FakeSocket);

const { useCompose } = await import("./useCompose");

const PLAN = {
  type: "plan",
  title: "Evening",
  key: "A minor",
  tempo: 88,
  time_signature: "3/4",
  kit: "brush",
  total_bars: 6,
};

const PATCH: Patch = {
  oscillator: "sine",
  attack: 0.1,
  decay: 0.2,
  sustain: 0.7,
  release: 0.5,
  filter_freq: 6000,
  filter_q: 2,
  reverb: 0.4,
  delay: 0,
};

/** The slice of BandEngine that useCompose actually touches. */
function fakeEngine() {
  const current = {
    buffer: { push: vi.fn() },
    startLive: vi.fn(),
    endAt: vi.fn(),
    stop: vi.fn(),
    applyPatches: vi.fn(),
    playSong: vi.fn(),
  };
  return { current } as unknown as React.RefObject<BandEngine | null> & {
    current: typeof current;
  };
}

async function started(engine = fakeEngine()) {
  const hook = renderHook(() => useCompose(engine, async () => {}));
  await act(() => hook.result.current.start("a slow waltz"));
  act(() => FakeSocket.instances[0].open());
  return { ...hook, engine, socket: FakeSocket.instances[0] };
}

describe("useCompose", () => {
  beforeEach(() => {
    FakeSocket.instances = [];
  });

  it("sends the brief once the socket opens", async () => {
    const { socket, result } = await started();

    expect(socket.url).toMatch(/\/ws\/compose$/);
    expect(socket.messages).toContainEqual({ type: "compose", brief: "a slow waltz" });
    expect(result.current.status).toBe("writing");
  });

  it("starts playing in the plan's meter after four bars, then assembles the song", async () => {
    const { socket, engine, result } = await started();

    act(() => socket.emit(PLAN));
    act(() => [0, 1, 2].forEach((i) => socket.emit({ type: "bar", bar: bar(i) })));
    expect(engine.current.startLive).not.toHaveBeenCalled();

    act(() => socket.emit({ type: "bar", bar: bar(3, { violin: { ...part("violin", [67], 3), patch: PATCH } }) }));
    expect(engine.current.startLive).toHaveBeenCalledWith(88, expect.any(Function), "3/4");
    expect(engine.current.applyPatches).toHaveBeenCalledWith({ violin: PATCH });
    expect(result.current.written).toBe(4);

    act(() => [4, 5].forEach((i) => socket.emit({ type: "bar", bar: bar(i) })));
    act(() => socket.emit({ type: "done" }));

    await waitFor(() => expect(result.current.status).toBe("done"));
    expect(engine.current.buffer.push).toHaveBeenCalledTimes(6);
    expect(engine.current.startLive).toHaveBeenCalledTimes(1);
    expect(result.current.song).toMatchObject({
      title: "Evening",
      kit: "brush",
      time_signature: "3/4",
      patches: { violin: PATCH },
    });
    expect(result.current.song?.bars).toHaveLength(6);
  });

  it("plays a piece shorter than the head start once it is all written", async () => {
    const { socket, engine } = await started();

    act(() => socket.emit({ ...PLAN, total_bars: 2 }));
    act(() => [0, 1].forEach((i) => socket.emit({ type: "bar", bar: bar(i) })));

    expect(engine.current.startLive).toHaveBeenCalledTimes(1);
  });

  it("surfaces a backend error", async () => {
    const { socket, result } = await started();

    act(() => socket.emit({ type: "error", detail: "provider is down" }));

    await waitFor(() => expect(result.current.error).toBe("provider is down"));
    expect(result.current.status).toBe("error");
  });

  it("reports a frame it cannot read instead of crashing", async () => {
    const { socket, result } = await started();

    act(() => socket.emit({ type: "bar", bar: { index: "three" } }));

    await waitFor(() => expect(result.current.error).toMatch(/cannot read/));
  });

  it("falls back to the blocking request when the socket never opens", async () => {
    const engine = fakeEngine();
    const written = { title: "Fallback", key: "C", tempo: 90, time_signature: "4/4", patches: {}, bars: [] };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(written))));
    const { result } = renderHook(() => useCompose(engine, async () => {}));
    await act(() => result.current.start("anything"));

    await act(async () => FakeSocket.instances[0].onerror?.());

    expect(result.current.song?.title).toBe("Fallback");
    expect(engine.current.playSong).toHaveBeenCalled();
    vi.unstubAllGlobals();
    vi.stubGlobal("WebSocket", FakeSocket);
  });

  it("stops the engine and closes the socket", async () => {
    const { socket, engine, result } = await started();

    act(() => result.current.stop());

    expect(socket.readyState).toBe(3);
    expect(engine.current.stop).toHaveBeenCalled();
  });
});
