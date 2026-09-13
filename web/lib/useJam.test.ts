import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { BandEngine } from "@/lib/audio/engine";
import type { Patch } from "@/lib/audio/types";
import { bar, part } from "@/lib/testing/fixtures";

/** A WebSocket double the tests drive directly. */
class FakeSocket {
  static instances: FakeSocket[] = [];
  static OPEN = 1;

  readyState = 0;
  sent: string[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: (() => void) | null = null;

  constructor(readonly url: string) {
    FakeSocket.instances.push(this);
  }

  send(payload: string) {
    this.sent.push(payload);
  }

  close() {
    this.readyState = 3;
    this.onclose?.();
  }

  open() {
    this.readyState = 1;
    this.onopen?.();
  }

  emit(message: object) {
    this.onmessage?.({ data: JSON.stringify(message) });
  }

  get messages(): object[] {
    return this.sent.map((s) => JSON.parse(s));
  }
}

vi.stubGlobal("WebSocket", FakeSocket);

const { useJam } = await import("./useJam");

/** The slice of BandEngine that useJam actually touches. */
function fakeEngine() {
  const current = {
    buffer: { push: vi.fn() },
    startLive: vi.fn(),
    stop: vi.fn(),
    setTempo: vi.fn(),
    applyPatches: vi.fn(),
  };
  return { current } as unknown as React.RefObject<BandEngine | null> & {
    current: typeof current;
  };
}

describe("useJam", () => {
  beforeEach(() => {
    FakeSocket.instances = [];
  });

  it("starts idle", () => {
    const { result } = renderHook(() => useJam(fakeEngine()));

    expect(result.current.status).toBe("idle");
    expect(FakeSocket.instances).toHaveLength(0);
  });

  it("connects and goes live when the socket opens", async () => {
    const engine = fakeEngine();
    const { result } = renderHook(() => useJam(engine));

    act(() => result.current.start(120));
    expect(result.current.status).toBe("connecting");

    act(() => FakeSocket.instances[0].open());

    await waitFor(() => expect(result.current.status).toBe("live"));
    expect(engine.current.startLive).toHaveBeenCalledWith(120, expect.any(Function));
  });

  it("does not open a second socket", () => {
    const { result } = renderHook(() => useJam(fakeEngine()));

    act(() => result.current.start(120));
    act(() => result.current.start(120));

    expect(FakeSocket.instances).toHaveLength(1);
  });

  it("pushes arriving bars into the engine buffer", async () => {
    const engine = fakeEngine();
    const { result } = renderHook(() => useJam(engine));
    act(() => result.current.start(120));
    act(() => FakeSocket.instances[0].open());

    act(() => FakeSocket.instances[0].emit({ type: "bar", bar: bar(3) }));

    expect(engine.current.buffer.push).toHaveBeenCalledWith(expect.objectContaining({ index: 3 }));
    await waitFor(() => expect(result.current.bars.get(3)).toBeDefined());
  });

  it("applies patches an agent wrote mid-bar", () => {
    const engine = fakeEngine();
    const { result } = renderHook(() => useJam(engine));
    act(() => result.current.start(120));
    act(() => FakeSocket.instances[0].open());

    const patch: Patch = {
      oscillator: "fmsine",
      attack: 0.1,
      decay: 0.2,
      sustain: 0.7,
      release: 0.5,
      filter_freq: 6000,
      filter_q: 2,
      reverb: 0.4,
      delay: 0,
    };
    const withPatch = bar(4, { violin: { ...part("violin", [67], 4), patch } });

    act(() => FakeSocket.instances[0].emit({ type: "bar", bar: withPatch }));

    expect(engine.current.applyPatches).toHaveBeenCalledWith({ violin: patch });
  });

  it("ignores patch application when no agent changed its sound", () => {
    const engine = fakeEngine();
    const { result } = renderHook(() => useJam(engine));
    act(() => result.current.start(120));
    act(() => FakeSocket.instances[0].open());

    act(() => FakeSocket.instances[0].emit({ type: "bar", bar: bar(0, { keys: part("keys", [60]) }) }));

    expect(engine.current.applyPatches).not.toHaveBeenCalled();
  });

  it("exposes the bandleader's cue", async () => {
    const { result } = renderHook(() => useJam(fakeEngine()));
    act(() => result.current.start(120));
    act(() => FakeSocket.instances[0].open());

    const cue = { section: "chorus", chords: ["F", "C"], energy: 8, density: 6,
                  soloist: "flute", tacet: [], direction: "lift it" };
    act(() => FakeSocket.instances[0].emit({ type: "cue", bar: 8, cue }));

    await waitFor(() => expect(result.current.cue?.section).toBe("chorus"));
  });

  it("sends steering messages", () => {
    const { result } = renderHook(() => useJam(fakeEngine()));
    act(() => result.current.start(120));
    act(() => FakeSocket.instances[0].open());

    act(() => result.current.steer({ energy: 9, solo: "violin" }));

    expect(FakeSocket.instances[0].messages).toContainEqual({
      type: "steer",
      energy: 9,
      solo: "violin",
    });
  });

  it("asks the backend for bars when the engine runs low", () => {
    const engine = fakeEngine();
    const { result } = renderHook(() => useJam(engine));
    act(() => result.current.start(120));
    act(() => FakeSocket.instances[0].open());

    const [, onNeedBars] = engine.current.startLive.mock.calls[0];
    act(() => onNeedBars(12));

    expect(FakeSocket.instances[0].messages).toContainEqual({
      type: "need_bars",
      from_bar: 12,
    });
  });

  it("follows a tempo change from the server", () => {
    const engine = fakeEngine();
    const { result } = renderHook(() => useJam(engine));
    act(() => result.current.start(120));
    act(() => FakeSocket.instances[0].open());

    act(() => FakeSocket.instances[0].emit({ type: "steered", tempo: 145, steer: {} }));

    expect(engine.current.setTempo).toHaveBeenCalledWith(145);
  });

  it("surfaces a backend error instead of hanging silently", async () => {
    const { result } = renderHook(() => useJam(fakeEngine()));
    act(() => result.current.start(120));
    act(() => FakeSocket.instances[0].open());

    act(() => FakeSocket.instances[0].emit({ type: "error", detail: "provider is down" }));

    await waitFor(() => expect(result.current.error).toBe("provider is down"));
  });

  it("clears everything on stop", async () => {
    const engine = fakeEngine();
    const { result } = renderHook(() => useJam(engine));
    act(() => result.current.start(120));
    act(() => FakeSocket.instances[0].open());
    act(() => FakeSocket.instances[0].emit({ type: "bar", bar: bar(0) }));

    act(() => result.current.stop());

    expect(FakeSocket.instances[0].messages).toContainEqual({ type: "stop" });
    expect(engine.current.stop).toHaveBeenCalled();
    await waitFor(() => {
      expect(result.current.status).toBe("idle");
      expect(result.current.bars.size).toBe(0);
    });
  });

  it("reports a socket error", async () => {
    const { result } = renderHook(() => useJam(fakeEngine()));
    act(() => result.current.start(120));

    act(() => FakeSocket.instances[0].onerror?.());

    await waitFor(() => expect(result.current.status).toBe("error"));
  });

  it("closes the socket when the page unmounts", () => {
    const { result, unmount } = renderHook(() => useJam(fakeEngine()));
    act(() => result.current.start(120));
    act(() => FakeSocket.instances[0].open());

    unmount();

    expect(FakeSocket.instances[0].readyState).toBe(3);
  });
});
