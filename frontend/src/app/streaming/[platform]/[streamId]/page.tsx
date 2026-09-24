import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { StreamRoom } from "@/components/stream-room";
import type { Platform } from "@/lib/api";

type Props = {
  params: Promise<{ platform: string; streamId: string }>;
};

const PLATFORMS = new Set<Platform>(["youtube", "twitch"]);
const YOUTUBE_ID_RE = /^[\w-]{11}$/;
const TWITCH_LOGIN_RE = /^[a-zA-Z0-9_]{1,25}$/;

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { platform, streamId } = await params;
  return {
    title: `${platform}/${streamId} · yt-stream-vibes`,
  };
}

export default async function StreamingPage({ params }: Props) {
  const { platform: rawPlatform, streamId: rawId } = await params;
  const platform = rawPlatform.toLowerCase() as Platform;
  const streamId = decodeURIComponent(rawId);

  if (!PLATFORMS.has(platform)) {
    notFound();
  }
  if (platform === "youtube" && !YOUTUBE_ID_RE.test(streamId)) {
    notFound();
  }
  if (platform === "twitch" && !TWITCH_LOGIN_RE.test(streamId)) {
    notFound();
  }

  return <StreamRoom platform={platform} streamId={streamId} />;
}
