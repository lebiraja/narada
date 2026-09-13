import Link from "next/link";

import { TrackLanes } from "@/components/TrackLanes";
import { BlurFade } from "@/components/ui/blur-fade";
import { INSTRUMENTS } from "@/lib/audio/types";
import { PLAYER } from "@/lib/palette";

const ROOMS = [
  {
    href: "/compose",
    name: "Write a piece",
    line: "Tell the bandleader what you want. The band works out the parts and plays it back.",
  },
  {
    href: "/jam",
    name: "Play live",
    line: "The band keeps going. Change the energy, hand out a solo, sit someone down.",
  },
  {
    href: "/studio",
    name: "Record a take",
    line: "Capture what you hear. Leave with an audio file and five separate MIDI parts.",
  },
];

export default function Home() {
  return (
    <main className="relative z-10 mx-auto max-w-5xl px-6 pb-20 pt-16 sm:pt-24">
      <BlurFade delay={0.05} inView>
        <h1 className="font-display text-[3.5rem] leading-[0.92] tracking-tight sm:text-[5.5rem]">
          A band that has
          <br />
          <em className="italic text-brass">never met</em>
        </h1>
      </BlurFade>

      <BlurFade delay={0.18} inView>
        <p className="mt-7 max-w-[34rem] text-[0.95rem] leading-relaxed text-bone/65">
          Five instruments, five AI musicians, one bandleader deciding the harmony and
          who takes the solo. They write their parts bar by bar while you listen.
        </p>
      </BlurFade>

      <BlurFade delay={0.32} inView>
        <div className="mt-14 border-y border-bone/10 py-5">
          <TrackLanes />
        </div>
      </BlurFade>

      <BlurFade delay={0.45} inView>
        <dl className="mt-6 flex flex-wrap gap-x-7 gap-y-2">
          {INSTRUMENTS.map((instrument) => (
            <div key={instrument} className="flex items-baseline gap-2">
              <dt className="text-[0.8rem]" style={{ color: PLAYER[instrument].hue }}>
                {PLAYER[instrument].name}
              </dt>
              <dd className="text-[0.8rem] text-bone/40">{PLAYER[instrument].role}</dd>
            </div>
          ))}
        </dl>
      </BlurFade>

      <BlurFade delay={0.55} inView>
        <nav className="mt-16 grid gap-px bg-bone/10 sm:grid-cols-3">
          {ROOMS.map((room) => (
            <Link
              key={room.href}
              href={room.href}
              className="group bg-stage p-6 transition-colors hover:bg-riser"
            >
              <span className="font-display text-2xl group-hover:text-brass">{room.name}</span>
              <span className="mt-2 block text-[0.85rem] leading-relaxed text-bone/50">
                {room.line}
              </span>
            </Link>
          ))}
        </nav>
      </BlurFade>
    </main>
  );
}
