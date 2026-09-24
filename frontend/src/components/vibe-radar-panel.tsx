"use client";

import { useEffect, useMemo, useState } from "react";
import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";
import { statsEventsUrl, type StatsEvent } from "@/lib/api";

type Props = {
  sessionId: string | null;
};

const EMPTY_LABELS = [
  "Laughs",
  "Hype",
  "Troll",
  "Support",
  "Tension",
  "Curiosity",
];

export function VibeRadarPanel({ sessionId }: Props) {
  const [stats, setStats] = useState<StatsEvent | null>(null);
  const [status, setStatus] = useState<"idle" | "connecting" | "live" | "error">(
    "idle",
  );
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setStats(null);
    setError(null);

    if (!sessionId) {
      setStatus("idle");
      return;
    }

    setStatus("connecting");
    const es = new EventSource(statsEventsUrl(sessionId));

    es.onopen = () => setStatus("live");

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as StatsEvent;
        if (data.error) {
          setError(data.error);
          setStatus("error");
          return;
        }
        setStats(data);
      } catch {
        setError("Bad SSE payload");
        setStatus("error");
      }
    };

    es.onerror = () => {
      setStatus("error");
      setError("SSE disconnected");
      es.close();
    };

    return () => es.close();
  }, [sessionId]);

  const labels = stats?.radar_data?.labels ?? EMPTY_LABELS;
  const values = stats?.radar_data?.datasets?.[0]?.data ?? labels.map(() => 0);
  const spamPct =
    typeof stats?.spam_rate === "number"
      ? Math.round(stats.spam_rate * 100)
      : null;

  const option = useMemo<EChartsOption>(
    () => ({
      animationDuration: 280,
      animationDurationUpdate: 280,
      radar: {
        indicator: labels.map((name) => ({ name, max: 100 })),
        center: ["50%", "52%"],
        radius: "62%",
        axisName: {
          color: "#8b9aab",
          fontSize: 10,
          fontFamily: "var(--font-jetbrains), ui-monospace, monospace",
        },
        splitLine: { lineStyle: { color: "#24303a" } },
        splitArea: {
          areaStyle: { color: ["transparent", "rgba(36,48,58,0.35)"] },
        },
        axisLine: { lineStyle: { color: "#24303a" } },
      },
      series: [
        {
          type: "radar",
          data: [
            {
              value: values,
              name: "Stream Vibe %",
              areaStyle: { color: "rgba(61,255,181,0.18)" },
              lineStyle: { color: "#3dffb5", width: 2 },
              itemStyle: { color: "#3dffb5" },
            },
          ],
        },
      ],
    }),
    [labels, values],
  );

  return (
    <section className="flex min-h-0 min-w-0 flex-col overflow-hidden border border-border bg-surface">
      <div className="flex shrink-0 items-center justify-between gap-2 border-b border-border px-3 py-2">
        <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted">
          Stream vibe
        </span>
        <div className="flex items-center gap-3">
          {typeof stats?.hype_score === "number" ? (
            <span className="font-mono text-[10px] tabular-nums text-accent">
              hype {stats.hype_score}
            </span>
          ) : null}
          <span
            className={`font-mono text-[10px] uppercase tracking-wider ${
              status === "live"
                ? "text-accent"
                : status === "error"
                  ? "text-live"
                  : "text-muted"
            }`}
          >
            {status === "live" ? "SSE · stats" : status}
          </span>
        </div>
      </div>

      <div className="flex min-h-0 flex-1 flex-col overflow-hidden bg-bg p-3">
        {!sessionId ? (
          <p className="font-mono text-xs text-muted">
            Start a session to stream vibe stats…
          </p>
        ) : error ? (
          <p className="font-mono text-xs text-live">{error}</p>
        ) : (
          <>
            <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
              <p className="font-mono text-xs text-fg">
                <span className="text-muted">Top vibe </span>
                {stats?.top_vibe ?? "—"}
              </p>
              {spamPct != null ? (
                <p className="font-mono text-[10px] tabular-nums text-muted">
                  spam {spamPct}%
                  {stats?.window
                    ? ` · ${stats.window.message_count} msgs / ${stats.window.seconds}s`
                    : ""}
                </p>
              ) : null}
            </div>
            <div className="min-h-[260px] flex-1">
              <ReactECharts
                option={option}
                style={{ height: "100%", width: "100%", minHeight: 260 }}
                opts={{ renderer: "canvas" }}
                notMerge
              />
            </div>
          </>
        )}
      </div>
    </section>
  );
}
