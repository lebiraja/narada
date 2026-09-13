import Link from "next/link";

const ROOMS = [
  {
    href: "/compose",
    index: "01",
    name: "COMPOSER",
    line: "Give the bandleader a brief. Get back a full five-part arrangement.",
  },
  {
    href: "/jam",
    index: "02",
    name: "LIVE JAM",
    line: "The band plays without stopping. You steer energy, mood and solos.",
  },
  {
    href: "/studio",
    index: "03",
    name: "STUDIO",
    line: "Record what you hear. Export a mixdown and five MIDI stems.",
  },
];

export default function Home() {
  return (
    <main className="mx-auto max-w-4xl px-6 py-20 sm:py-28">
      <p className="text-xs uppercase tracking-[0.4em] text-bone/40">
        Five instruments · Five agents
      </p>
      <h1 className="mt-6 text-[13vw] leading-[0.85] tracking-tighter sm:text-8xl">
        AI
        <br />
        <span className="text-ember">BAND</span>
      </h1>
      <p className="mt-8 max-w-lg text-sm leading-relaxed text-bone/60">
        Drums, keyboard, guitar, flute and violin — each played by its own agent,
        under a bandleader that decides harmony, form and who takes the solo.
      </p>

      <nav className="mt-16 border-t border-bone/10">
        {ROOMS.map((room) => (
          <Link
            key={room.href}
            href={room.href}
            className="group flex items-baseline gap-6 border-b border-bone/10 py-6 transition-colors hover:bg-bone/[0.03]"
          >
            <span className="text-xs text-bone/30 group-hover:text-ember">{room.index}</span>
            <span className="flex-1">
              <span className="block text-2xl tracking-tight group-hover:text-ember">
                {room.name}
              </span>
              <span className="mt-1 block text-xs text-bone/50">{room.line}</span>
            </span>
            <span className="text-bone/20 transition-transform group-hover:translate-x-1 group-hover:text-ember">
              →
            </span>
          </Link>
        ))}
      </nav>
    </main>
  );
}
