"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { connectStream, fetchLives } from "@/lib/api";

export function useLives(q: string) {
  const query = q.trim();
  return useQuery({
    queryKey: ["lives", query],
    queryFn: () => fetchLives(query),
    enabled: query.length >= 2,
  });
}

export function useConnectStream() {
  return useMutation({
    mutationFn: (videoId: string) => connectStream(videoId),
  });
}
