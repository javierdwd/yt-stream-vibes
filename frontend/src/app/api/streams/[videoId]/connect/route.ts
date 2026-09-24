import { backendUrl } from "@/lib/backend";

export const dynamic = "force-dynamic";

type Params = { params: Promise<{ videoId: string }> };

export async function POST(_request: Request, { params }: Params) {
  const { videoId } = await params;
  const res = await fetch(backendUrl(`/api/streams/${encodeURIComponent(videoId)}/connect`), {
    method: "POST",
    cache: "no-store",
  });
  const data = await res.json();
  return Response.json(data, { status: res.status });
}
