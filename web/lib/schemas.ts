import { z } from "zod";

import { INSTRUMENTS } from "./audio/types";

/** Everything the backend sends is parsed here before the app touches it. */

export const InstrumentSchema = z.enum(INSTRUMENTS);

export const NoteSchema = z.object({
  pitch: z.number(),
  start: z.number(),
  dur: z.number(),
  vel: z.number().nullable(),
  step: z.number().nullish(),
  len: z.number().nullish(),
  articulation: z.string().nullish(),
  piece: z.string().nullish(),
  slur: z.boolean().optional(),
});

export const PatchSchema = z.object({
  oscillator: z.enum(["sine", "square", "sawtooth", "triangle", "fmsine", "amsine"]),
  attack: z.number(),
  decay: z.number(),
  sustain: z.number(),
  release: z.number(),
  filter_freq: z.number(),
  filter_q: z.number(),
  reverb: z.number(),
  delay: z.number(),
});

export const BarPartSchema = z.object({
  instrument: InstrumentSchema,
  bar: z.number(),
  notes: z.array(NoteSchema),
  patch: PatchSchema.nullable(),
});

export const BarSchema = z.object({
  index: z.number(),
  chord: z.string(),
  parts: z.partialRecord(InstrumentSchema, BarPartSchema),
});

export const SongSchema = z.object({
  title: z.string(),
  key: z.string(),
  tempo: z.number(),
  time_signature: z.string(),
  kit: z.string().optional(),
  patches: z.partialRecord(InstrumentSchema, PatchSchema),
  bars: z.array(BarSchema),
});

export const CueSchema = z.object({
  section: z.string(),
  chords: z.array(z.string()),
  energy: z.number(),
  density: z.number(),
  soloist: InstrumentSchema.nullable(),
  tacet: z.array(InstrumentSchema),
  direction: z.string(),
});

const ErrorMessage = z.object({ type: z.literal("error"), detail: z.string() });
const BarMessage = z.object({ type: z.literal("bar"), bar: BarSchema });

export const JamMessageSchema = z.discriminatedUnion("type", [
  z.object({
    type: z.literal("session"),
    id: z.string(),
    tempo: z.number(),
    key: z.string().nullish(),
    time_signature: z.string().nullish(),
  }),
  z.object({ type: z.literal("cue"), cue: CueSchema }),
  BarMessage,
  z.object({ type: z.literal("steered"), tempo: z.number() }),
  ErrorMessage,
]);

export const PlanSchema = z.object({
  type: z.literal("plan"),
  title: z.string(),
  key: z.string(),
  tempo: z.number(),
  time_signature: z.string(),
  kit: z.string(),
  total_bars: z.number(),
});

export const ComposeMessageSchema = z.discriminatedUnion("type", [
  PlanSchema,
  BarMessage,
  z.object({ type: z.literal("done") }),
  ErrorMessage,
]);

export type Cue = z.infer<typeof CueSchema>;
export type Plan = z.infer<typeof PlanSchema>;
export type JamMessage = z.infer<typeof JamMessageSchema>;
export type ComposeMessage = z.infer<typeof ComposeMessageSchema>;

/** What the user sees when a frame or response does not match the contract. */
export const MALFORMED = "The band sent something this page cannot read.";
