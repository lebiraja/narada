import Link from "next/link";

export function Chrome({ name, children }: { name: string; children: React.ReactNode }) {
  return (
    <main className="relative z-10 mx-auto max-w-4xl px-6 pb-24 pt-10">
      <header className="flex items-baseline justify-between border-b border-bone/10 pb-4">
        <h1 className="font-display text-2xl tracking-tight">{name}</h1>
        <Link
          href="/"
          className="text-[0.8rem] text-bone/45 underline-offset-4 hover:text-brass hover:underline"
        >
          Back to the band
        </Link>
      </header>
      {children}
    </main>
  );
}
