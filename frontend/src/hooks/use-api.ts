import { connectStream, fetchLives, type Platform } from "@/lib/api";
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

export function useLives(limit = 24) {
  return useQuery({
    queryKey: ["lives", limit],
    queryFn: () => fetchLives(limit),
    staleTime: 300_000,
    retry: 1,
  });
}
