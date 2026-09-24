export default function Home() {
  return (
    <main className="flex flex-1 flex-col gap-6 px-6 py-10 md:px-10">
      <header className="flex items-baseline justify-between border-b border-border pb-4">
        <h1 className="text-2xl font-semibold tracking-tight text-fg md:text-3xl">
          yt-stream-vibes
        </h1>
        <p className="font-mono text-xs uppercase tracking-widest text-muted">
          Signal Room
        </p>
      </header>

      <section className="grid gap-4 border border-border bg-surface p-5 transition-colors duration-200 hover:border-accent/40">
        <p className="text-sm text-muted">Scaffold ready</p>
        <p className="max-w-xl text-base leading-relaxed text-fg/90">
          Next.js + Tailwind frontend talking to FastAPI over REST and SSE via
          Next.js API routes. Wire country selector, top lives, and live metrics
          next.
        </p>
        <p className="font-mono text-xs text-accent">Browser → /api/* → FastAPI</p>
      </section>
    </main>
  );
}
