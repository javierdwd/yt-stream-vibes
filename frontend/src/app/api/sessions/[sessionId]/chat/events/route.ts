import { backendUrl } from "@/lib/backend";

export const dynamic = "force-dynamic";

type Params = { params: Promise<{ sessionId: string }> };

export async function GET(_request: Request, { params }: Params) {
  const { sessionId } = await params;
  const upstream = await fetch(
    backendUrl(`/api/sessions/${encodeURIComponent(sessionId)}/chat/events`),
    {
      headers: { Accept: "text/event-stream" },
      cache: "no-store",
    },
  );

  if (!upstream.ok || !upstream.body) {
    return Response.json(
      { detail: "Upstream SSE unavailable" },
      { status: upstream.status || 502 },
    );
  }

  return new Response(upstream.body, {
    status: upstream.status,
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
