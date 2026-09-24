"use client";

import { useEffect, useState } from "react";
import { LiveSearch } from "@/components/live-search";
import { StreamStrip } from "@/components/stream-strip";
import { useLives } from "@/hooks/use-api";

export function LivesPanel() {
  const [input, setInput] = useState("");
  const [q, setQ] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const { data, isLoading, isFetching, error, refetch, isFetched } = useLives(q);

  useEffect(() => {
    const handle = window.setTimeout(() => {
      const next = input.trim();
      setQ(next);
      setSelectedId(null);
    }, 350);
    return () => window.clearTimeout(handle);
  }, [input]);

  const tooShort = q.length > 0 && q.length < 2;
  const idle = q.length < 2;

  return (
    <section className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-4 border-b border-border pb-4">
        <LiveSearch value={input} onChange={setInput} />
        <div className="flex items-center gap-3">
          {(isLoading || isFetching) && !idle && (
            <span className="font-mono text-[10px] uppercase tracking-widest text-muted">
              Syncing
            </span>
          )}
          <button
            type="button"
            onClick={() => refetch()}
            disabled={idle}
            className="h-9 border border-border px-3 font-mono text-xs uppercase tracking-wider text-muted transition-colors duration-200 hover:border-accent/50 hover:text-accent disabled:cursor-not-allowed disabled:opacity-40"
          >
            Refresh
          </button>
        </div>
      </div>

      {idle ? (
        <p className="border border-dashed border-border px-4 py-8 text-sm text-muted">
          {tooShort
            ? "Type at least 2 characters."
            : "Search for a live channel or topic — same idea as YouTube search with Live on."}
        </p>
      ) : error ? (
        <div className="border border-live/40 bg-live/5 px-4 py-3 text-sm text-fg">
          <p className="font-mono text-[10px] uppercase tracking-widest text-live">
            Search failed
          </p>
          <p className="mt-1 text-muted">
            {error instanceof Error ? error.message : "Request failed"}
          </p>
        </div>
      ) : isLoading && !isFetched ? (
        <p className="border border-border px-4 py-8 font-mono text-sm text-muted">
          Searching lives…
        </p>
      ) : (
        <StreamStrip
          streams={data?.streams ?? []}
          selectedId={selectedId}
          onSelect={setSelectedId}
        />
      )}
    </section>
  );
}
