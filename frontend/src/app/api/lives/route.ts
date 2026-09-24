import { backendUrl } from "@/lib/backend";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const q = new URL(request.url).searchParams.get("q")?.trim();
  if (!q) {
    return Response.json({ detail: "q is required" }, { status: 400 });
  }

  const res = await fetch(
    backendUrl(`/api/lives?q=${encodeURIComponent(q)}`),
    { cache: "no-store" },
  );
  const data = await res.json();
  return Response.json(data, { status: res.status });
}
