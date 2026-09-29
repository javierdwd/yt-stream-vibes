"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";
import { WordCloud, type Word } from "@isoterik/react-word-cloud";
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

const WORD_FILL = ["#3dffb5", "#e8eef4", "#8b9aab", "#ff5c7a"] as const;

export function VibeRadarPanel({ sessionId }: Props) {
  const [stats, setStats] = useState<StatsEvent | null>(null);
  const [status, setStatus] = useState<"idle" | "connecting" | "live" | "error">(
    "idle",
  );
  const [error, setError] = useState<string | null>(null);
  const cloudHostRef = useRef<HTMLDivElement | null>(null);
  const [cloudSize, setCloudSize] = useState({ width: 0, height: 0 });

  useEffect(() => {
    const el = cloudHostRef.current;
    if (!el) {
      setCloudSize({ width: 0, height: 0 });
      return;
    }
    const update = () => {
      setCloudSize({ width: el.clientWidth, height: el.clientHeight });
    };
    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, [sessionId, stats?.word_cloud?.length ?? 0]);

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
        if (data.heartbeat) return;
        if (data.error) {
          setError(data.error);
          setStatus("error");
          return;
        }
        setStats(data);
        setStatus("live");
        setError(null);
      } catch {
        setError("Bad SSE payload");
        setStatus("error");
      }
    };

    es.onerror = () => {
      // Let EventSource retry transient drops; only surface a hard close.
      if (es.readyState === EventSource.CLOSED) {
        setStatus("error");
        setError("SSE disconnected");
        return;
      }
      setStatus("connecting");
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
  const wordCloudKey = JSON.stringify(stats?.word_cloud ?? []);
  const words: Word[] = useMemo(() => {
    const raw = JSON.parse(wordCloudKey) as Array<{ text: string; value: number }>;
    return raw.map((w) => ({ text: w.text, value: w.value }));
  }, [wordCloudKey]);
  const wordMin = words.reduce(
    (m, w) => Math.min(m, w.value),
    Number.POSITIVE_INFINITY,
  );
  const wordMax = words.reduce(
    (m, w) => Math.max(m, w.value),
    Number.NEGATIVE_INFINITY,
  );
  // Concrete family for canvas measure + SVG paint (CSS vars break d3 layout → overlap).
  const cloudFont = "JetBrains Mono, ui-monospace, monospace";
  const resolveFontSize = (word: Word) => {
    const span = Math.min(cloudSize.width, cloudSize.height);
    const minPx = Math.max(12, Math.round(span * 0.08));
    const maxPx = Math.max(minPx + 6, Math.round(span * 0.22));
    if (!Number.isFinite(wordMin) || !Number.isFinite(wordMax)) return minPx;
    if (wordMax <= wordMin) return Math.round((minPx + maxPx) / 2);
    const t = (word.value - wordMin) / (wordMax - wordMin);
    return Math.round(minPx + t * (maxPx - minPx));
  };

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
        // Room for bar value labels above the peak so they aren't clipped.
        top: 22,
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
                <span className="text-muted">Topic streamer </span>
                {stats?.streamer_topic ?? "—"}
              </p>
              <p className="font-mono text-[10px] leading-snug text-fg">
                <span className="text-muted">Topic chat </span>
                {stats?.chat_topic ?? "—"}
              </p>
            </div>
            <div className="grid min-h-[220px] flex-[1.15] grid-rows-2 gap-2">
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
            <div className="flex min-h-[180px] flex-1 flex-col overflow-hidden border border-border bg-surface/40">
              <p className="shrink-0 px-2 pt-1.5 font-mono text-[10px] uppercase tracking-[0.14em] text-muted">
                Keywords
              </p>
              <div ref={cloudHostRef} className="relative min-h-0 flex-1 px-1 pb-1">
                {words.length === 0 ? (
                  <p className="px-1 pt-2 font-mono text-[10px] text-muted">
                    Waiting for keywords…
                  </p>
                ) : cloudSize.width > 0 && cloudSize.height > 0 ? (
                  <WordCloud
                    words={words}
                    width={Math.floor(cloudSize.width)}
                    height={Math.floor(cloudSize.height)}
                    font={cloudFont}
                    fontWeight="600"
                    fontSize={resolveFontSize}
                    spiral="archimedean"
                    rotate={() => 0}
                    padding={3}
                    fill={(_word, index) => WORD_FILL[index % WORD_FILL.length]}
                    svgProps={{
                      style: {
                        display: "block",
                        width: "100%",
                        height: "100%",
                      },
                      "aria-label": "Chat keyword word cloud",
                    }}
                  />
                ) : null}
              </div>
            </div>
          </>
        )}
      </div>
    </section>
  );
}
