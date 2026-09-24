import { backendUrl } from "@/lib/backend";

export const dynamic = "force-dynamic";

type Params = { params: Promise<{ sessionId: string }> };

export async function DELETE(_request: Request, { params }: Params) {
  const { sessionId } = await params;
  const res = await fetch(
    backendUrl(`/api/sessions/${encodeURIComponent(sessionId)}`),
    {
      method: "DELETE",
      cache: "no-store",
    },
  );

  if (res.status === 204) {
    return new Response(null, { status: 204 });
  }

  const text = await res.text().catch(() => "");
  return new Response(text, {
    status: res.status,
    headers: { "Content-Type": res.headers.get("Content-Type") ?? "text/plain" },
  });
}
