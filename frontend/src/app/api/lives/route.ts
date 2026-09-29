import { backendUrl } from "@/lib/backend";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const incoming = new URL(request.url);
  const qs = incoming.searchParams.toString();
  const path = qs ? `/api/lives?${qs}` : "/api/lives";
  const res = await fetch(backendUrl(path), {
    headers: { Accept: "application/json" },
    cache: "no-store",
  });
  const data = await res.text();
  return new Response(data, {
    status: res.status,
    headers: {
      "Content-Type": res.headers.get("Content-Type") ?? "application/json",
    },
  });
}
