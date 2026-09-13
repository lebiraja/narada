import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

/** Unmount between tests so queries never match a previous render. */
afterEach(cleanup);

/** jsdom has no Web Audio; Tone.js is mocked per-test where it matters. */
if (!globalThis.AudioContext) {
  globalThis.AudioContext = vi.fn() as unknown as typeof AudioContext;
}

if (!globalThis.URL.createObjectURL) {
  globalThis.URL.createObjectURL = vi.fn(() => "blob:mock");
  globalThis.URL.revokeObjectURL = vi.fn();
}
