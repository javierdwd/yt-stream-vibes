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
    <section className="shrink-0 border-b border-border pb-6">
      <div className="max-w-2xl">
        <h2 className="text-lg font-semibold tracking-tight text-fg md:text-xl">
          Paste a live URL
        </h2>
        <p className="mt-1 font-mono text-[11px] text-muted">
          Or pick a top live below to open the Signal Room.
        </p>
      </div>

      <form
        onSubmit={(e) => void onSubmit(e)}
        className="mt-4 flex max-w-2xl flex-col gap-3 sm:flex-row sm:items-center"
      >
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
          className="h-10 w-full border border-border bg-surface px-3 font-mono text-sm text-fg outline-none transition-colors duration-200 placeholder:text-muted/70 focus:border-accent"
        />
        <button
          type="submit"
          disabled={busy || !url.trim()}
          className="h-10 shrink-0 border border-border px-4 font-mono text-xs uppercase tracking-wider text-accent transition-colors duration-200 hover:border-accent disabled:cursor-not-allowed disabled:opacity-40"
        >
          {busy ? "Resolving…" : "Open"}
        </button>
      </form>
      {error ? (
        <p className="mt-2 font-mono text-xs text-live">{error}</p>
      ) : null}
    </section>
  );
}
