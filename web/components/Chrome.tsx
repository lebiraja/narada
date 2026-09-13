import Link from "next/link";

export function Chrome({
  index,
  name,
  children,
}: {
  index: string;
  name: string;
  children: React.ReactNode;
}) {
  return (
    <main className="mx-auto max-w-5xl px-6 py-12">
      <header className="flex items-baseline justify-between border-b border-bone/10 pb-4">
        <h1 className="flex items-baseline gap-4 tracking-tight">
          <span className="text-xs text-bone/30">{index}</span>
          <span className="text-xl">{name}</span>
        </h1>
        <Link href="/" className="text-xs text-bone/40 hover:text-ember">
          ← BAND
        </Link>
      </header>
      {children}
    </main>
  );
}
