import * as Tone from "tone";

import { INSTRUMENTS, type Instrument } from "./types";

interface ChannelSettings {
  pan: number;
  highpass: number;
  send: number;
  mudCut: boolean;
}

/**
 * Starting mix. Pans spread the band around a centred kit and bass, which
 * stay nearly dry to keep the low end tight; highpasses keep each part out of the kick's low end, and the
 * airy leads sit further back in the shared room than the rhythm section.
 */
const MIX: Record<Instrument, ChannelSettings> = {
  drums: { pan: 0, highpass: 30, send: 0.08, mudCut: false },
  bass: { pan: 0, highpass: 30, send: 0.05, mudCut: false },
  keys: { pan: -0.25, highpass: 80, send: 0.2, mudCut: true },
  guitar: { pan: 0.3, highpass: 90, send: 0.2, mudCut: true },
  flute: { pan: 0.15, highpass: 200, send: 0.35, mudCut: false },
  violin: { pan: -0.15, highpass: 180, send: 0.35, mudCut: false },
};

interface Channel {
  input: Tone.Gain;
  send: Tone.Gain;
  nodes: Tone.ToneAudioNode[];
}

/**
 * The master bus: one channel per instrument (gain, highpass, optional
 * low-mid cut, pan) summed into a gentle glue compressor and a limiter,
 * with a single shared reverb fed by per-channel sends.
 */
export class Mixer {
  private channels = new Map<Instrument, Channel>();
  private reverb: Tone.Reverb;
  private compressor: Tone.Compressor;
  private limiter: Tone.Limiter;

  constructor() {
    this.limiter = new Tone.Limiter(-1).toDestination();
    this.compressor = new Tone.Compressor({
      threshold: -18,
      ratio: 2,
      attack: 0.03,
      release: 0.25,
    }).connect(this.limiter);
    this.reverb = new Tone.Reverb({ decay: 1.6, wet: 1 }).connect(this.compressor);

    for (const instrument of INSTRUMENTS) {
      const settings = MIX[instrument];
      const input = new Tone.Gain(0.8);
      const highpass = new Tone.Filter(settings.highpass, "highpass");
      const panner = new Tone.Panner(settings.pan).connect(this.compressor);
      const send = new Tone.Gain(settings.send).connect(this.reverb);
      const nodes: Tone.ToneAudioNode[] = [input, highpass, panner, send];

      input.connect(highpass);
      if (settings.mudCut) {
        const cut = new Tone.Filter({ type: "peaking", frequency: 300, Q: 1, gain: -2.5 });
        highpass.connect(cut);
        cut.connect(panner);
        nodes.push(cut);
      } else {
        highpass.connect(panner);
      }
      panner.connect(send);

      this.channels.set(instrument, { input, send, nodes });
    }
  }

  /** The node an instrument's voice plays into. */
  channel(instrument: Instrument): Tone.ToneAudioNode {
    return this.channels.get(instrument)!.input;
  }

  setVolume(instrument: Instrument, value: number): void {
    this.channels.get(instrument)?.input.gain.rampTo(value, 0.05);
  }

  /** How much of an instrument reaches the shared reverb, 0..1. */
  setSend(instrument: Instrument, amount: number): void {
    this.channels.get(instrument)?.send.gain.rampTo(amount, 0.05);
  }

  dispose(): void {
    for (const { nodes } of this.channels.values()) {
      for (const node of nodes) node.dispose();
    }
    this.channels.clear();
    this.reverb.dispose();
    this.compressor.dispose();
    this.limiter.dispose();
  }
}
