/** Browser-facing API client — always hits Next.js `/api/*`, never FastAPI. */

export type LiveStream = {
  video_id: string;
  title: string;
  channel: string;
  thumbnail_url: string;
  concurrent_viewers: number | null;
};

export type LivesResponse = {
  q: string;
  platform?: string;
  streams: LiveStream[];
  detail?: string;
};

export type ConnectResponse = {
  session_id: string;
  video_id: string;
  platform?: string;
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
  sentiment?: string | null;
  hype_score?: number | null;
  vibe?: string | null;
  spam?: boolean | null;
  spam_reason?: string | null;
};

export type ChatBatchEvent = {
  session_id?: string;
  video_id: string;
  platform?: string;
  messages: ChatMessage[];
  error?: string;
  classify_error?: string;
};

export type StatsEvent = {
  session_id?: string;
  video_id: string;
  platform?: string;
  chart_type?: "radar";
  radar_data?: {
    labels: string[];
    datasets: Array<{ label: string; data: number[] }>;
  };
  top_vibe?: string | null;
  hype_score?: number;
  sentiment?: { positive: number; neutral: number; negative: number };
  questions?: Array<{ id: string; author: string; message: string }>;
  spam_rate?: number;
  spam_count?: number;
  window?: {
    seconds: number;
    message_count: number;
    non_spam_count?: number;
  };
  error?: string;
  classify_error?: string;
};

async function apiJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: {
      Accept: "application/json",
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

export function fetchLives(q: string): Promise<LivesResponse> {
  const params = new URLSearchParams({ q });
  return apiJson(`/api/lives?${params}`);
}

export function connectStream(videoId: string): Promise<ConnectResponse> {
  return apiJson(`/api/streams/${encodeURIComponent(videoId)}/connect`, {
    method: "POST",
  });
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
