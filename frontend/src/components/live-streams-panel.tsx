"use client";

import Image from "next/image";
import Link from "next/link";
import { YoutubeAttribution } from "@/components/youtube-attribution";
import { useLives } from "@/hooks/use-api";
import type { LiveStream } from "@/lib/api";

function formatViewers(n: number | null): string {
  if (n == null) return "—";
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function StreamTile({ stream }: { stream: LiveStream }) {
  const href = `/streaming/${encodeURIComponent(stream.platform)}/${encodeURIComponent(stream.stream_id)}`;
  const viewers = formatViewers(stream.concurrent_viewers);
  const chatters =
    typeof stream.chat_authors === "number"
      ? formatViewers(stream.chat_authors)
      : null;

  return (
    <Link
      href={href}
      className="group flex flex-col border border-border bg-surface outline-none transition-colors duration-200 hover:border-accent focus-visible:border-accent"
    >
      <div className="relative aspect-video overflow-hidden bg-bg">
        {stream.thumbnail_url ? (
          <Image
            src={stream.thumbnail_url}
            alt=""
            fill
            sizes="(max-width: 768px) 50vw, 12.5vw"
            className="object-cover transition-opacity duration-200 group-hover:opacity-90"
            unoptimized
          />
        ) : (
          <div className="absolute inset-0 bg-border/40" />
        )}
        <span className="absolute left-2 top-2 inline-flex items-center gap-1.5 bg-bg/80 px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-widest text-fg">
          <span
            className="h-1.5 w-1.5 animate-pulse rounded-full bg-live"
            aria-hidden
          />
          Live
        </span>
      </div>
      <div className="flex min-h-0 flex-1 flex-col gap-1.5 px-2.5 py-2">
        <p className="line-clamp-2 text-sm leading-snug text-fg transition-colors duration-200 group-hover:text-accent">
          {stream.title || "Untitled stream"}
        </p>
        <div className="mt-auto flex items-baseline justify-between gap-2">
          <p className="min-w-0 truncate font-mono text-[11px] text-muted">
            {stream.channel}
          </p>
          <p
            className="shrink-0 font-mono text-[11px] tabular-nums text-accent"
            title={
              [
                stream.concurrent_viewers != null
                  ? `${stream.concurrent_viewers.toLocaleString()} watching`
                  : null,
                typeof stream.chat_authors === "number"
                  ? `${stream.chat_authors.toLocaleString()} in recent chat sample`
                  : null,
              ]
                .filter(Boolean)
                .join(" · ") || undefined
            }
          >
            {viewers}
            <span className="ml-1 text-muted">viewing</span>
            {chatters != null ? (
              <>
                <span className="mx-1 text-muted/50">·</span>
                {chatters}
                <span className="ml-1 text-muted">chat</span>
              </>
            ) : null}
          </p>
        </div>
      </div>
    </Link>
  );
}

function SkeletonGrid() {
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-4">
      {Array.from({ length: 8 }).map((_, i) => (
        <div
          key={i}
          className="animate-pulse border border-border bg-surface"
          aria-hidden
        >
          <div className="aspect-video bg-border/30" />
          <div className="space-y-2 px-2.5 py-2">
            <div className="h-3 w-3/4 bg-border/40" />
            <div className="h-2.5 w-1/2 bg-border/30" />
          </div>
        </div>
      ))}
    </div>
  );
}

export function LiveStreamsPanel() {
  const { data, isLoading, isError, error, refetch, isFetching } = useLives(24);
  const streams = data?.streams ?? [];

  return (
    <section className="flex min-h-0 flex-1 flex-col gap-4 overflow-hidden">
      <div className="flex shrink-0 items-center gap-3">
        <h2 className="text-lg font-semibold leading-none tracking-tight text-fg md:text-xl">
          Top Lives
        </h2>
        <div className="ml-auto flex items-center gap-4">
          <YoutubeAttribution height={24} />
          <button
            type="button"
            onClick={() => void refetch()}
            disabled={isFetching}
            className="font-mono text-[11px] uppercase leading-none tracking-wider text-muted transition-colors duration-200 hover:text-accent disabled:opacity-40"
          >
            {isFetching ? "Refreshing…" : "Refresh"}
          </button>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto pr-1">
        {isLoading ? <SkeletonGrid /> : null}

        {isError ? (
          <p className="font-mono text-xs text-live">
            {error instanceof Error ? error.message : "Failed to load lives"}
          </p>
        ) : null}

        {!isLoading && !isError && streams.length === 0 ? (
          <p className="font-mono text-xs text-muted">No live streams found.</p>
        ) : null}

        {!isLoading && streams.length > 0 ? (
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4">
            {streams.map((stream) => (
              <StreamTile key={stream.stream_id} stream={stream} />
            ))}
          </div>
        ) : null}
      </div>
    </section>
  );
}
