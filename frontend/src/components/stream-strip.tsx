"use client";

import Image from "next/image";
import Link from "next/link";
import type { LiveStream } from "@/lib/api";

type Props = {
  streams: LiveStream[];
};

function formatViewers(n: number | null): string {
  if (n == null) return "—";
  return new Intl.NumberFormat("en", {
    notation: n >= 10_000 ? "compact" : "standard",
    maximumFractionDigits: 1,
  }).format(n);
}

export function StreamStrip({ streams }: Props) {
  if (streams.length === 0) {
    return (
      <p className="border border-dashed border-border px-4 py-8 text-sm text-muted">
        No live streams match this search right now.
      </p>
    );
  }

  return (
    <ul className="grid gap-2 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
      {streams.map((stream) => (
        <li key={stream.video_id}>
          <Link
            href={`/streaming/${stream.video_id}`}
            className="group flex w-full flex-col overflow-hidden border border-border bg-surface/60 text-left transition-colors duration-200 hover:border-accent/40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
          >
            <div className="relative aspect-video w-full bg-bg">
              {stream.thumbnail_url ? (
                <Image
                  src={stream.thumbnail_url}
                  alt=""
                  fill
                  sizes="(max-width: 640px) 100vw, 20vw"
                  className="object-cover opacity-90 transition-opacity duration-200 group-hover:opacity-100"
                />
              ) : null}
              <span className="absolute left-2 top-2 inline-flex items-center gap-1.5 bg-bg/85 px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider text-live">
                <span
                  className="size-1.5 animate-pulse rounded-full bg-live"
                  aria-hidden
                />
                Live
              </span>
            </div>
            <div className="flex flex-1 flex-col gap-1 border-t border-border p-2.5">
              <p className="line-clamp-2 text-sm leading-snug text-fg">
                {stream.title}
              </p>
              <p className="truncate text-xs text-muted">{stream.channel}</p>
              <p className="mt-auto font-mono text-xs tabular-nums text-accent">
                {formatViewers(stream.concurrent_viewers)}
                <span className="ml-1 text-muted">viewers</span>
              </p>
            </div>
          </Link>
        </li>
      ))}
    </ul>
  );
}
