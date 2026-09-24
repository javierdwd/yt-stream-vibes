import { backendUrl } from "@/lib/backend";

export const dynamic = "force-dynamic";

type Params = { params: Promise<{ streamId: string }> };

export async function POST(request: Request, { params }: Params) {
  const { streamId } = await params;
  const url = new URL(request.url);
  const platform = url.searchParams.get("platform") || "youtube";
  const qs = new URLSearchParams({ platform });
  const res = await fetch(
    backendUrl(
      `/api/streams/${encodeURIComponent(streamId)}/connect?${qs}`,
    ),
    {
      method: "POST",
      cache: "no-store",
    },
  );
  const data = await res.json();
  return Response.json(data, { status: res.status });
}
