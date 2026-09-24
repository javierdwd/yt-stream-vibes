import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { StreamRoom } from "@/components/stream-room";

type Props = {
  params: Promise<{ videoId: string }>;
};

/** YouTube video IDs are 11 chars from [A-Za-z0-9_-]. */
const VIDEO_ID_RE = /^[\w-]{11}$/;

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { videoId } = await params;
  return {
    title: `Stream ${videoId} · yt-stream-vibes`,
  };
}

export default async function StreamingPage({ params }: Props) {
  const { videoId } = await params;
  if (!VIDEO_ID_RE.test(videoId)) {
    notFound();
  }

  return <StreamRoom videoId={videoId} />;
}
