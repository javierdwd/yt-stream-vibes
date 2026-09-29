"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { IdleSessionGuard } from "@/components/idle-session-guard";
import { IngestedChatFeed } from "@/components/ingested-chat-feed";
import { VibeRadarPanel } from "@/components/vibe-radar-panel";
import { YoutubeAttribution } from "@/components/youtube-attribution";
import { clearSession, connectStream, type Platform } from "@/lib/api";

type Props = {
  platform: Platform;
  streamId: string;
};

export function StreamRoom({ platform, streamId }: Props) {
  const [embedDomain, setEmbedDomain] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const sessionRef = useRef<string | null>(null);

  useEffect(() => {
    setEmbedDomain(window.location.hostname);
  }, []);

  useEffect(() => {
    sessionRef.current = sessionId;
  }, [sessionId]);

  const startSession = useCallback(async () => {
    setBusy(true);
    setActionError(null);
    try {
      const existing = sessionRef.current;
      if (existing) {
        await clearSession(existing).catch(() => undefined);
        setSessionId(null);
      }
      const res = await connectStream(platform, streamId);
      setSessionId(res.session_id);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Connect failed");
    } finally {
      setBusy(false);
    }
  }, [platform, streamId]);

  const onClear = useCallback(async () => {
    const id = sessionRef.current;
    if (!id) return;
    setBusy(true);
    setActionError(null);
    try {
      await clearSession(id);
      setSessionId(null);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Clear failed");
    } finally {
      setBusy(false);
    }
  }, []);

  const onIdleDisconnect = useCallback(async () => {
    const id = sessionRef.current;
    if (!id) return;
    setActionError(null);
    try {
      await clearSession(id);
    } catch {
      // Session may already be gone server-side.
    } finally {
      setSessionId(null);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      setBusy(true);
      setActionError(null);
      try {
        const res = await connectStream(platform, streamId);
        if (cancelled) {
          await clearSession(res.session_id).catch(() => undefined);
          return;
        }
        setSessionId(res.session_id);
      } catch (err) {
        if (!cancelled) {
          setActionError(err instanceof Error ? err.message : "Connect failed");
        }
      } finally {
        if (!cancelled) setBusy(false);
      }
    })();

    return () => {
      cancelled = true;
      const id = sessionRef.current;
      if (id) {
        void clearSession(id).catch(() => undefined);
      }
      setSessionId(null);
    };
  }, [platform, streamId]);

  const playerSrc =
    platform === "youtube"
      ? `https://www.youtube.com/embed/${encodeURIComponent(streamId)}?autoplay=1&rel=0`
      : embedDomain != null
        ? `https://player.twitch.tv/?channel=${encodeURIComponent(streamId)}&parent=${encodeURIComponent(embedDomain)}&muted=false`
        : null;

  return (
    <main className="flex h-full min-h-0 flex-1 flex-col gap-3 overflow-hidden px-3 py-3 md:gap-4 md:px-6 md:py-4">
      <IdleSessionGuard
        sessionId={sessionId}
        onIdleDisconnect={onIdleDisconnect}
        onReconnect={() => void startSession()}
      />
      <header className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-b border-border pb-2">
        <div className="flex min-w-0 flex-wrap items-center gap-3">
          <Link
            href="/"
            className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted transition-colors duration-200 hover:text-accent"
          >
            ← Signal Room
          </Link>
          <h1 className="text-lg font-semibold tracking-tight text-fg md:text-xl">
            Stream
          </h1>
          {platform === "youtube" ? <YoutubeAttribution height={20} /> : null}
        </div>
        <div className="flex flex-wrap items-center gap-2 md:gap-3">
          {sessionId ? (
            <span className="inline-flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-wider text-live">
              <span className="size-1.5 animate-pulse rounded-full bg-live" aria-hidden />
              On air
            </span>
          ) : (
            <span className="font-mono text-[10px] uppercase tracking-wider text-muted">
              Idle
            </span>
          )}
          <span className="font-mono text-[10px] uppercase tracking-wider text-muted">
            {platform}
          </span>
          <code className="font-mono text-xs text-muted">{streamId}</code>
          {sessionId ? (
            <button
              type="button"
              onClick={() => void onClear()}
              disabled={busy}
              className="border border-border px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.14em] text-fg transition-colors duration-200 hover:border-live hover:text-live disabled:opacity-50"
            >
              Clear
            </button>
          ) : (
            <button
              type="button"
              onClick={() => void startSession()}
              disabled={busy}
              className="border border-border px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.14em] text-accent transition-colors duration-200 hover:border-accent disabled:opacity-50"
            >
              Start
            </button>
          )}
        </div>
      </header>

      {actionError ? (
        <p className="shrink-0 truncate font-mono text-xs text-live">{actionError}</p>
      ) : null}

      <div className="grid min-h-0 flex-1 grid-cols-1 grid-rows-[minmax(0,1.2fr)_minmax(0,1fr)_minmax(0,1fr)] gap-2 overflow-hidden md:gap-3 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)_minmax(0,1fr)] lg:grid-rows-1">
        <section className="flex min-h-0 min-w-0 flex-col overflow-hidden border border-border bg-surface">
          <div className="shrink-0 border-b border-border px-3 py-2 font-mono text-[10px] uppercase tracking-[0.18em] text-muted">
            Player
          </div>
          <div className="relative min-h-0 flex-1 bg-bg">
            {playerSrc ? (
              <iframe
                title={`${platform} live player`}
                src={playerSrc}
                className="absolute inset-0 h-full w-full"
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                allowFullScreen
                referrerPolicy="strict-origin-when-cross-origin"
              />
            ) : (
              <p className="p-4 font-mono text-xs text-muted">Loading player…</p>
            )}
          </div>
        </section>

        <IngestedChatFeed sessionId={sessionId} />
        <VibeRadarPanel sessionId={sessionId} />
      </div>
    </main>
  );
}
