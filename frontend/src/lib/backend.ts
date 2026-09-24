/** Server-only FastAPI base URL. Never import this into client components. */
export function backendUrl(path: string): string {
  const base = (process.env.API_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
  return `${base}${path.startsWith("/") ? path : `/${path}`}`;
}
