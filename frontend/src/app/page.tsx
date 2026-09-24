import { LivesPanel } from "@/components/lives-panel";

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

      <LivesPanel />
    </main>
  );
}
