import { backendUrl } from "@/lib/backend";

export const dynamic = "force-dynamic";

export async function GET() {
  const res = await fetch(backendUrl("/health"), { cache: "no-store" });
  const data = await res.json();
  return Response.json(data, { status: res.status });
}
