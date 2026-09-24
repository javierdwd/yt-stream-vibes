"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { connectStream, fetchLives } from "@/lib/api";

export function useLives(regionCode: string) {
  return useQuery({
    queryKey: ["lives", regionCode],
    queryFn: () => fetchLives(regionCode),
    enabled: regionCode.length === 2,
  });
}

export function useConnectStream() {
  return useMutation({
    mutationFn: (videoId: string) => connectStream(videoId),
  });
}
