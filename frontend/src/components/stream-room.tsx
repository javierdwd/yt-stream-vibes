"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { IngestedChatFeed } from "@/components/ingested-chat-feed";

type Props = {
  videoId: string;
};

export function StreamRoom({ videoId }: Props) {
  const [embedDomain, setEmbedDomain] = useState<string | null>(null);

  useEffect(() => {
    setEmbedDomain(window.location.hostname);
  }, []);

  const playerSrc = `https://www.youtube.com/embed/${encodeURIComponent(videoId)}?autoplay=1&rel=0`;
  const chatSrc =
    embedDomain != null
      ? `https://www.youtube.com/live_chat?v=${encodeURIComponent(videoId)}&embed_domain=${encodeURIComponent(embedDomain)}&dark_theme=1`
      : null;

  return (
    <main className="flex min-h-full flex-1 flex-col gap-4 px-4 py-6 md:px-8 md:py-8">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-3">
        <div className="flex items-baseline gap-4">
          <Link
            href="/"
            className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted transition-colors duration-200 hover:text-accent"
          >
            ← Signal Room
          </Link>
          <h1 className="text-lg font-semibold tracking-tight text-fg md:text-xl">
            Stream
          </h1>
        </div>
        <div className="flex items-center gap-3">
          <span className="inline-flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-wider text-live">
            <span className="size-1.5 animate-pulse rounded-full bg-live" aria-hidden />
            On air
          </span>
          <code className="font-mono text-xs text-muted">{videoId}</code>
        </div>
      </header>

      <div className="grid min-h-0 flex-1 gap-3 lg:grid-cols-[minmax(0,1.2fr)_minmax(240px,320px)_minmax(240px,320px)] lg:items-stretch">
        <section className="flex min-h-0 flex-col border border-border bg-surface">
          <div className="border-b border-border px-3 py-2 font-mono text-[10px] uppercase tracking-[0.18em] text-muted">
            Player
          </div>
          <div className="relative aspect-video w-full bg-bg lg:aspect-auto lg:min-h-[420px] lg:flex-1">
            <iframe
              title="YouTube live player"
              src={playerSrc}
              className="absolute inset-0 h-full w-full"
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
              allowFullScreen
              referrerPolicy="strict-origin-when-cross-origin"
            />
          </div>
        </section>

        <section className="flex min-h-[420px] flex-col border border-border bg-surface lg:min-h-0">
          <div className="border-b border-border px-3 py-2 font-mono text-[10px] uppercase tracking-[0.18em] text-muted">
            Official chat
          </div>
          <div className="relative min-h-0 flex-1 bg-bg">
            {chatSrc ? (
              <iframe
                title="YouTube live chat"
                src={chatSrc}
                className="absolute inset-0 h-full w-full"
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                referrerPolicy="strict-origin-when-cross-origin"
              />
            ) : (
              <p className="p-4 font-mono text-xs text-muted">Loading chat…</p>
            )}
          </div>
        </section>

        <IngestedChatFeed videoId={videoId} />
      </div>
    </main>
  );
}
