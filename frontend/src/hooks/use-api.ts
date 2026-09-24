import { connectStream, type Platform } from "@/lib/api";
import { useQuery } from "@tanstack/react-query";

export function useConnect(platform: Platform, streamId: string) {
  return useQuery({
    queryKey: ["connect", platform, streamId],
    queryFn: () => connectStream(platform, streamId),
    enabled: Boolean(platform && streamId),
    staleTime: Infinity,
    retry: 1,
  });
}
