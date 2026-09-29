"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { resolveStreamUrl } from "@/lib/api";

export function UrlPastePanel() {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = url.trim();
    if (!trimmed) return;
    setBusy(true);
    setError(null);
    try {
      const resolved = await resolveStreamUrl(trimmed);
      router.push(
        `/streaming/${encodeURIComponent(resolved.platform)}/${encodeURIComponent(resolved.stream_id)}`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Resolve failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="flex min-h-0 flex-1 flex-col justify-center gap-6">
      <div className="max-w-2xl">
        <h2 className="text-xl font-semibold tracking-tight text-fg md:text-2xl">
          Paste a live URL
        </h2>
        <p className="mt-2 font-mono text-xs text-muted">
          Drop a live stream link to open the Signal Room.
        </p>
      </div>

      <form onSubmit={(e) => void onSubmit(e)} className="flex max-w-2xl flex-col gap-3">
        <label className="sr-only" htmlFor="stream-url">
          Stream URL
        </label>
        <input
          id="stream-url"
          type="url"
          inputMode="url"
          autoComplete="off"
          spellCheck={false}
          placeholder="https://www.youtube.com/watch?v=…"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          className="h-11 w-full border border-border bg-surface px-3 font-mono text-sm text-fg outline-none transition-colors duration-200 placeholder:text-muted/70 focus:border-accent"
        />
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="submit"
            disabled={busy || !url.trim()}
            className="h-9 border border-border px-4 font-mono text-xs uppercase tracking-wider text-accent transition-colors duration-200 hover:border-accent disabled:cursor-not-allowed disabled:opacity-40"
          >
            {busy ? "Resolving…" : "Open stream"}
          </button>
          {error ? (
            <p className="font-mono text-xs text-live">{error}</p>
          ) : null}
        </div>
      </form>
    </section>
  );
}
