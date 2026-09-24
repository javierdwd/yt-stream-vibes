"use client";

import { useEffect, useRef, useState } from "react";
import {
  streamEventsUrl,
  type ChatBatchEvent,
  type ChatMessage,
} from "@/lib/api";

type Props = {
  videoId: string;
};

const MAX_MESSAGES = 200;

function sentimentClass(s: string | null | undefined): string {
  if (s === "positive") return "text-pos";
  if (s === "negative") return "text-neg";
  if (s === "neutral") return "text-neu";
  return "text-muted";
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

export function IngestedChatFeed({ videoId }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [hype, setHype] = useState(0);
  const [status, setStatus] = useState<"connecting" | "live" | "error">("connecting");
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setMessages([]);
    setHype(0);
    setStatus("connecting");
    setError(null);

    const es = new EventSource(streamEventsUrl(videoId));

    es.onopen = () => setStatus("live");

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as ChatBatchEvent;
        if (data.error) {
          setError(data.error);
          setStatus("error");
          return;
        }
        const batch = data.messages ?? [];
        // Ignore empty heartbeats so hype/gauge don't reset during quiet chat.
        if (batch.length === 0) return;

        if (typeof data.hype_score === "number") {
          setHype(data.hype_score);
        }
        setMessages((prev) => mergeMessages(prev, batch));
      } catch {
        setError("Bad SSE payload");
        setStatus("error");
      }
    };

    es.onerror = () => {
      setStatus("error");
      setError("SSE disconnected");
      es.close();
    };

    return () => es.close();
  }, [videoId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <section className="flex min-h-[420px] flex-col border border-border bg-surface lg:min-h-0">
      <div className="flex items-center justify-between gap-2 border-b border-border px-3 py-2">
        <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted">
          Ingested + JEV
        </span>
        <div className="flex items-center gap-3">
          <span className="font-mono text-[10px] tabular-nums text-accent">
            hype {hype}
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
            {status === "live" ? "SSE · JEV" : status}
          </span>
        </div>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto bg-bg p-2 font-mono text-xs">
        {error ? (
          <p className="text-live">{error}</p>
        ) : messages.length === 0 ? (
          <p className="text-muted">Waiting for messages…</p>
        ) : (
          <ul className="flex flex-col gap-1.5">
            {messages.map((m) => (
              <li
                key={m.id}
                className={`border-b border-border/60 pb-1.5 last:border-0 ${
                  m.spam || m.intent === "spam" ? "opacity-45" : ""
                }`}
              >
                <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                  <span className="text-accent">{m.author || "anon"}</span>
                  {m.spam || m.intent === "spam" ? (
                    <span className="text-[10px] uppercase tracking-wide text-live">
                      spam{m.spam_reason ? `:${m.spam_reason}` : ""}
                    </span>
                  ) : m.intent ? (
                    <span className="text-[10px] uppercase tracking-wide text-muted">
                      {m.intent}
                    </span>
                  ) : null}
                  {m.sentiment && !(m.spam || m.intent === "spam") ? (
                    <span
                      className={`text-[10px] uppercase tracking-wide ${sentimentClass(m.sentiment)}`}
                    >
                      {m.sentiment}
                    </span>
                  ) : null}
                  {typeof m.hype_score === "number" &&
                  !(m.spam || m.intent === "spam") ? (
                    <span className="text-[10px] tabular-nums text-muted">
                      h{m.hype_score}
                    </span>
                  ) : null}
                </div>
                <p className="mt-0.5 break-words text-fg/90">{m.message}</p>
              </li>
            ))}
          </ul>
        )}
        <div ref={bottomRef} />
      </div>
    </section>
  );
}
