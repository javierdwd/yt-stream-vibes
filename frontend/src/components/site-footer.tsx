import Link from "next/link";
import { YoutubeAttribution } from "@/components/youtube-attribution";

export function SiteFooter() {
  return (
    <footer className="shrink-0 border-t border-border px-6 py-2 md:px-10">
      <div className="flex items-center justify-between gap-4">
        <div className="flex min-w-0 items-center gap-3">
          <p className="font-mono text-[10px] uppercase tracking-widest text-muted/70">
            yt-stream-vibes
          </p>
          <YoutubeAttribution height={20} />
        </div>
        <nav className="flex items-center gap-3">
          <Link
            href="/terms"
            className="font-mono text-[10px] uppercase tracking-widest text-muted transition-colors duration-200 hover:text-accent focus-visible:text-accent focus-visible:outline-none"
          >
            Terms
          </Link>
          <Link
            href="/privacy"
            className="font-mono text-[10px] uppercase tracking-widest text-muted transition-colors duration-200 hover:text-accent focus-visible:text-accent focus-visible:outline-none"
          >
            Privacy
          </Link>
        </nav>
      </div>
    </footer>
  );
}
