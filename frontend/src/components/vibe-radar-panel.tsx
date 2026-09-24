"use client";

import { useEffect, useMemo, useState } from "react";
import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";
import { statsEventsUrl, type StatsEvent } from "@/lib/api";

type Props = {
  sessionId: string | null;
};

const VIBE_ORDER = [
  "laughter_humor",
  "hype_pog",
  "troll_sarcasm",
  "support_wholesome",
  "tension_drama",
  "curiosity_context",
] as const;

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
  const pctValues = stats?.radar_data?.datasets?.[0]?.data ?? labels.map(() => 0);
  const countValues = VIBE_ORDER.map((key) =>
    Number(stats?.vibe_counts?.[key] ?? 0),
  );
  const spamPct =
    typeof stats?.spam_rate === "number"
      ? Math.round(stats.spam_rate * 100)
      : null;

  const radarOption = useMemo<EChartsOption>(
    () => ({
      animationDuration: 280,
      animationDurationUpdate: 280,
      radar: {
        indicator: labels.map((name) => ({ name, max: 100 })),
        center: ["50%", "55%"],
        radius: "68%",
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
              value: pctValues,
              name: "Stream Vibe %",
              areaStyle: { color: "rgba(61,255,181,0.18)" },
              lineStyle: { color: "#3dffb5", width: 2 },
              itemStyle: { color: "#3dffb5" },
            },
          ],
        },
      ],
    }),
    [labels, pctValues],
  );

  const barOption = useMemo<EChartsOption>(
    () => ({
      animationDuration: 280,
      animationDurationUpdate: 280,
      grid: {
        left: 8,
        right: 12,
        top: 8,
        bottom: 24,
        containLabel: true,
      },
      xAxis: {
        type: "category",
        data: labels,
        axisLabel: {
          color: "#8b9aab",
          fontSize: 10,
          fontFamily: "var(--font-jetbrains), ui-monospace, monospace",
          interval: 0,
        },
        axisLine: { lineStyle: { color: "#24303a" } },
        axisTick: { show: false },
      },
      yAxis: {
        type: "value",
        minInterval: 1,
        splitLine: { lineStyle: { color: "#24303a" } },
        axisLabel: {
          color: "#8b9aab",
          fontSize: 10,
          fontFamily: "var(--font-jetbrains), ui-monospace, monospace",
        },
      },
      series: [
        {
          type: "bar",
          data: countValues,
          barMaxWidth: 28,
          itemStyle: {
            color: "#3dffb5",
            borderRadius: [2, 2, 0, 0],
          },
          label: {
            show: true,
            position: "top",
            color: "#8b9aab",
            fontSize: 10,
            fontFamily: "var(--font-jetbrains), ui-monospace, monospace",
            formatter: "{c}",
          },
        },
      ],
    }),
    [labels, countValues],
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

      <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-hidden bg-bg p-3">
        {!sessionId ? (
          <p className="font-mono text-xs text-muted">
            Start a session to stream vibe stats…
          </p>
        ) : error ? (
          <p className="font-mono text-xs text-live">{error}</p>
        ) : (
          <>
            <div className="flex shrink-0 flex-wrap items-baseline justify-between gap-2">
              <p className="font-mono text-xs text-fg">
                <span className="text-muted">Top vibe </span>
                {stats?.top_vibe ?? "—"}
              </p>
              {spamPct != null ? (
                <p className="font-mono text-[10px] tabular-nums text-muted">
                  spam {spamPct}%
                  {stats?.window ? ` · ${stats.window.message_count} msgs` : ""}
                  {stats?.window?.span_seconds != null
                    ? ` · ${stats.window.span_seconds}s`
                    : ""}
                </p>
              ) : null}
            </div>
            <div className="shrink-0 space-y-1 border border-border bg-surface/40 px-2 py-1.5">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted">
                  Sync
                </p>
                {typeof stats?.alignment_score === "number" ? (
                  <p className="font-mono text-[10px] tabular-nums text-accent">
                    {stats.alignment_score}%
                    {stats.alignment_label ? ` · ${stats.alignment_label}` : ""}
                  </p>
                ) : (
                  <p className="font-mono text-[10px] text-muted">
                    {stats?.audio_error
                      ? stats.audio_error
                      : stats?.platform === "youtube"
                        ? "Listening…"
                        : "YouTube only"}
                  </p>
                )}
              </div>
              <p className="font-mono text-[10px] leading-snug text-fg">
                <span className="text-muted">topic </span>
                {stats?.theme_oneliner ?? "—"}
              </p>
              <p
                className="line-clamp-2 font-mono text-[10px] leading-snug text-muted"
                title={stats?.streamer_transcript ?? undefined}
              >
                <span className="text-muted/80">speech </span>
                {stats?.streamer_transcript ?? "—"}
              </p>
            </div>
            <div className="grid min-h-0 flex-1 grid-rows-2 gap-2">
              <div className="min-h-0">
                <p className="mb-1 font-mono text-[10px] uppercase tracking-[0.14em] text-muted">
                  Mix %
                </p>
                <ReactECharts
                  option={radarOption}
                  style={{ height: "calc(100% - 1rem)", width: "100%", minHeight: 100 }}
                  opts={{ renderer: "canvas" }}
                  notMerge
                />
              </div>
              <div className="min-h-0">
                <p className="mb-1 font-mono text-[10px] uppercase tracking-[0.14em] text-muted">
                  Totals
                </p>
                <ReactECharts
                  option={barOption}
                  style={{ height: "calc(100% - 1rem)", width: "100%", minHeight: 100 }}
                  opts={{ renderer: "canvas" }}
                  notMerge
                />
              </div>
            </div>
          </>
        )}
      </div>
    </section>
  );
}
