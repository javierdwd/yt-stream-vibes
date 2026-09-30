"use client";

import { useEffect, useRef, useState } from "react";
import {
  chatEventsUrl,
  type ChatBatchEvent,
  type ChatMessage,
} from "@/lib/api";

type Props = {
  sessionId: string | null;
};

const MAX_MESSAGES = 200;
const SPAM_PREVIEW_CHARS = 80;

function isSpamMessage(m: ChatMessage): boolean {
  return Boolean(m.spam || m.intent === "spam");
}

/** One-line preview for spam floods (emoji walls, etc.). */
function displayMessage(m: ChatMessage): string {
  if (!isSpamMessage(m)) return m.message || "";
  const raw = (m.message || "").replace(/\s+/g, " ").trim();
  if (raw.length <= SPAM_PREVIEW_CHARS) return raw;
  return `${raw.slice(0, SPAM_PREVIEW_CHARS)}…`;
}

function mergeMessages(prev: ChatMessage[], batch: ChatMessage[]): ChatMessage[] {
  const byId = new Map(prev.map((m) => [m.id, m]));
  for (const msg of batch) {
    if (!msg.id) continue;
    byId.set(msg.id, { ...byId.get(msg.id), ...msg });
  }
  const next = Array.from(byId.values());
  return next.length > MAX_MESSAGES ? next.slice(-MAX_MESSAGES) : next;
}

export function IngestedChatFeed({ sessionId }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [status, setStatus] = useState<"idle" | "connecting" | "live" | "error">(
    "idle",
  );
  const [error, setError] = useState<string | null>(null);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setMessages([]);
    setError(null);

    if (!sessionId) {
      setStatus("idle");
      return;
    }

    setStatus("connecting");
    const es = new EventSource(chatEventsUrl(sessionId));

    es.onopen = () => setStatus("live");

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as ChatBatchEvent;
        if (data.heartbeat) return;
        if (data.error) {
          setError(data.error);
          setStatus("error");
          return;
        }
        const batch = data.messages ?? [];
        if (batch.length === 0) return;
        setMessages((prev) => mergeMessages(prev, batch));
        setStatus("live");
        setError(null);
      } catch {
        setError("Bad SSE payload");
        setStatus("error");
      }
    };

    es.onerror = () => {
      if (es.readyState === EventSource.CLOSED) {
        setStatus("error");
        setError("SSE disconnected");
        return;
      }
      setStatus("connecting");
    };

    return () => es.close();
  }, [sessionId]);

  useEffect(() => {
    const el = listRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [messages]);

  return (
    <section className="flex min-h-0 min-w-0 flex-col overflow-hidden border border-border bg-surface">
      <div className="flex shrink-0 items-center justify-between gap-2 border-b border-border px-3 py-2">
        <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted">
          Ingested + JEV
        </span>
        <span
          className={`font-mono text-[10px] uppercase tracking-wider ${
            status === "live"
              ? "text-accent"
              : status === "error"
                ? "text-live"
                : "text-muted"
          }`}
        >
          {status === "live" ? "SSE · chat" : status}
        </span>
      </div>
      <div
        ref={listRef}
        className="min-h-0 flex-1 overflow-y-auto overscroll-contain bg-bg p-2 font-mono text-xs"
      >
        {!sessionId ? (
          <p className="text-muted">Start a session to ingest chat…</p>
        ) : error ? (
          <p className="text-live">{error}</p>
        ) : messages.length === 0 ? (
          <p className="text-muted">Waiting for messages…</p>
        ) : (
          <ul className="flex flex-col gap-1.5">
            {messages.map((m) => {
              const spam = isSpamMessage(m);
              return (
              <li
                key={m.id}
                className={`border-b border-border/60 pb-1.5 last:border-0 ${
                  spam ? "opacity-45" : ""
                }`}
              >
                <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                  <span className="text-accent">{m.author || "anon"}</span>
                  {spam ? (
                    <span className="text-[10px] uppercase tracking-wide text-live">
                      spam{m.spam_reason ? `:${m.spam_reason}` : ""}
                    </span>
                  ) : (
                    <>
                      {m.vibe ? (
                        <span className="text-[10px] uppercase tracking-wide text-muted">
                          {m.vibe}
                        </span>
                      ) : m.intent ? (
                        <span className="text-[10px] uppercase tracking-wide text-muted">
                          {m.intent}
                        </span>
                      ) : null}
                      {typeof m.hype_score === "number" ? (
                        <span className="text-[10px] tabular-nums text-muted">
                          h{m.hype_score}
                        </span>
                      ) : null}
                    </>
                  )}
                </div>
                <p
                  className={`mt-0.5 text-fg/90 ${
                    spam ? "truncate" : "break-words"
                  }`}
                  title={spam ? m.message || undefined : undefined}
                >
                  {displayMessage(m)}
                </p>
              </li>
              );
            })}
          </ul>
        )}
      </div>
    </section>
  );
}
