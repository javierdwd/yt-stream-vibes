/** Browser-facing API client — always hits Next.js `/api/*`, never FastAPI. */

export type Platform = "youtube" | "twitch";

export type ResolveResponse = {
  platform: Platform;
  stream_id: string;
  title: string;
  channel: string;
  thumbnail_url: string;
  concurrent_viewers: number | null;
  live: boolean;
  detail?: string;
};

export type ConnectResponse = {
  session_id: string;
  stream_id: string;
  video_id: string;
  platform: Platform;
  status: string;
  detail?: string;
};

export type ChatMessage = {
  id: string;
  author: string;
  message: string;
  timestamp: string;
  type: string;
  intent?: string | null;
  hype_score?: number | null;
  vibe?: string | null;
  spam?: boolean | null;
  spam_reason?: string | null;
};

export type ChatBatchEvent = {
  session_id?: string;
  video_id?: string;
  platform?: string;
  messages?: ChatMessage[];
  error?: string;
  classify_error?: string;
  heartbeat?: boolean;
};

export type StatsEvent = {
  session_id?: string;
  video_id?: string;
  platform?: string;
  chart_type?: "radar";
  radar_data?: {
    labels: string[];
    datasets: Array<{ label: string; data: number[] }>;
  };
  vibe_counts?: Record<string, number>;
  top_vibe?: string | null;
  hype_score?: number;
  spam_rate?: number;
  spam_count?: number;
  window?: {
    message_count: number;
    non_spam_count?: number;
    span_seconds?: number;
  };
  streamer_vibe?: string | null;
  streamer_topic?: string | null;
  chat_topic?: string | null;
  theme_oneliner?: string | null;
  word_cloud?: Array<{ text: string; value: number }>;
  alignment_score?: number | null;
  alignment_label?: string | null;
  audio_error?: string | null;
  error?: string;
  classify_error?: string;
  heartbeat?: boolean;
};

async function apiJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    try {
      const json = JSON.parse(text) as { detail?: unknown };
      if (typeof json.detail === "string" && json.detail) {
        throw new Error(json.detail);
      }
    } catch (err) {
      if (err instanceof Error && !(err instanceof SyntaxError)) throw err;
    }
    throw new Error(text || `${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export function resolveStreamUrl(url: string): Promise<ResolveResponse> {
  return apiJson("/api/streams/resolve", {
    method: "POST",
    body: JSON.stringify({ url }),
  });
}

export function connectStream(
  platform: Platform,
  streamId: string,
): Promise<ConnectResponse> {
  const params = new URLSearchParams({ platform });
  return apiJson(
    `/api/streams/${encodeURIComponent(streamId)}/connect?${params}`,
    { method: "POST" },
  );
}

export async function clearSession(sessionId: string): Promise<void> {
  const res = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}`, {
    method: "DELETE",
  });
  if (!res.ok && res.status !== 204) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `${res.status} ${res.statusText}`);
  }
}

export function chatEventsUrl(sessionId: string): string {
  return `/api/sessions/${encodeURIComponent(sessionId)}/chat/events`;
}

export function statsEventsUrl(sessionId: string): string {
  return `/api/sessions/${encodeURIComponent(sessionId)}/stats/events`;
}
