import type { Instrument } from "./audio/types";

/**
 * Each player keeps one hue everywhere in the app — meters, lanes, controls.
 * Colour is the identifier, so you can read the band at a glance.
 */
export const PLAYER: Record<Instrument, { hue: string; name: string; role: string }> = {
  drums: { hue: "#C9962E", name: "Drums", role: "keeps time" },
  keys: { hue: "#7A4B63", name: "Keyboard", role: "holds the harmony" },
  guitar: { hue: "#A6402D", name: "Guitar", role: "rhythm and colour" },
  flute: { hue: "#6B7F5C", name: "Flute", role: "a single voice" },
  violin: { hue: "#4A6D82", name: "Violin", role: "carries the melody" },
};
