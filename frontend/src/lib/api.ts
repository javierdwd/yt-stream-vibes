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
  video_id: string;
  status: string;
  detail?: string;
};

export type ChatMessage = {
  id: string;
  author: string;
  message: string;
  timestamp: string;
  type: string;
};

export type ChatBatchEvent = {
  video_id: string;
  messages: ChatMessage[];
  error?: string;
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

export function streamEventsUrl(videoId: string): string {
  return `/api/streams/${encodeURIComponent(videoId)}/events`;
}
