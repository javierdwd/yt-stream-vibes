"use client";

import { useEffect, useRef, useState } from "react";
import { streamEventsUrl, type ChatMessage } from "@/lib/api";

type Props = {
  videoId: string;
};

const MAX_MESSAGES = 200;

export function IngestedChatFeed({ videoId }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [status, setStatus] = useState<"connecting" | "live" | "error">("connecting");
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setMessages([]);
    setStatus("connecting");
    setError(null);

    const es = new EventSource(streamEventsUrl(videoId));

    es.onopen = () => setStatus("live");

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as {
          messages?: ChatMessage[];
          error?: string;
        };
        if (data.error) {
          setError(data.error);
          setStatus("error");
          return;
        }
        const batch = data.messages ?? [];
        if (batch.length === 0) return;
        setMessages((prev) => {
          const seen = new Set(prev.map((m) => m.id));
          const next = [...prev];
          for (const msg of batch) {
            if (!msg.id || seen.has(msg.id)) continue;
            seen.add(msg.id);
            next.push(msg);
          }
          return next.length > MAX_MESSAGES ? next.slice(-MAX_MESSAGES) : next;
        });
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
          Ingested chat
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
          {status === "live" ? "SSE · 3s" : status}
        </span>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto bg-bg p-2 font-mono text-xs">
        {error ? (
          <p className="text-live">{error}</p>
        ) : messages.length === 0 ? (
          <p className="text-muted">Waiting for messages…</p>
        ) : (
          <ul className="flex flex-col gap-1.5">
            {messages.map((m) => (
              <li key={m.id} className="border-b border-border/60 pb-1.5 last:border-0">
                <span className="text-accent">{m.author || "anon"}</span>
                <span className="text-muted"> · </span>
                <span className="text-fg/90 break-words">{m.message}</span>
              </li>
            ))}
          </ul>
        )}
        <div ref={bottomRef} />
      </div>
    </section>
  );
}
