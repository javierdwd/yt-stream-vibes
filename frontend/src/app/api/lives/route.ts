import { backendUrl } from "@/lib/backend";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const regionCode = new URL(request.url).searchParams.get("region_code");
  if (!regionCode) {
    return Response.json({ detail: "region_code is required" }, { status: 400 });
  }

  const res = await fetch(
    backendUrl(`/api/lives?region_code=${encodeURIComponent(regionCode)}`),
    { cache: "no-store" },
  );
  const data = await res.json();
  return Response.json(data, { status: res.status });
}
