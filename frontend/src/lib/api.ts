/** Browser-facing API client — always hits Next.js `/api/*`, never FastAPI. */

export type LiveStream = {
  video_id: string;
  title: string;
  channel: string;
  thumbnail_url: string;
  concurrent_viewers: number | null;
};

export type LivesResponse = {
  region_code: string;
  streams: LiveStream[];
  detail?: string;
};

export type ConnectResponse = {
  video_id: string;
  status: string;
  detail?: string;
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
    const body = await res.text().catch(() => "");
    throw new Error(body || `${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export function fetchLives(regionCode: string): Promise<LivesResponse> {
  const q = new URLSearchParams({ region_code: regionCode });
  return apiJson(`/api/lives?${q}`);
}

export function connectStream(videoId: string): Promise<ConnectResponse> {
  return apiJson(`/api/streams/${encodeURIComponent(videoId)}/connect`, {
    method: "POST",
  });
}

export function streamEventsUrl(videoId: string): string {
  return `/api/streams/${encodeURIComponent(videoId)}/events`;
}
