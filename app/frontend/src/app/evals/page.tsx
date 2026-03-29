"use client";

import { useState, useEffect } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
} from "recharts";
import { Header } from "@/components/header";
import { fetchEvals, type EvalsResponse } from "@/lib/api";

/** Short display name for an environment path like "primeintellect/gsm8k" */
function envLabel(env: string): string {
  const parts = env.split("/");
  return parts[parts.length - 1];
}

/** Format a score as percentage */
function fmt(v: number): string {
  return `${(v * 100).toFixed(1)}%`;
}

function EvalChart({
  env,
  baseline,
  chartData,
  hasData,
  position,
}: {
  env: string;
  baseline: number | null;
  chartData: { version: string; score: number; timestamp: string; adapter: string | null }[];
  hasData: boolean;
  position: "top-left" | "top-right" | "bottom-left" | "bottom-right";
}) {
  const borderClasses =
    position === "top-left"
      ? "border-r border-b border-border-custom"
      : position === "top-right"
        ? "border-b border-border-custom"
        : position === "bottom-left"
          ? "border-r border-border-custom"
          : "";

  return (
    <div className={`flex flex-col ${borderClasses}`}>
      {/* Section header — matches log-viewer / pipeline-panel style */}
      <div className="flex items-center justify-between border-b border-border-custom px-3 py-2">
        <h3 className="font-mono text-[11px] font-medium text-text-dim">
          {envLabel(env)}
        </h3>
        {baseline !== null && (
          <span className="font-mono text-[10px] text-text-dim">
            baseline: {fmt(baseline)}
          </span>
        )}
      </div>

      {/* Chart area */}
      <div className="flex flex-1 items-center justify-center p-3">
        {!hasData && baseline === null ? (
          <p className="text-center font-mono text-xs text-text-dim">
            No eval data yet.
          </p>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={
                hasData
                  ? chartData
                  : [{ version: "base", score: baseline ?? 0, timestamp: "", adapter: null }]
              }
              margin={{ top: 10, right: 10, left: 0, bottom: 5 }}
            >
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="var(--border)"
                opacity={0.5}
              />
              <XAxis
                dataKey="version"
                tick={{ fontSize: 10, fontFamily: "var(--font-mono)" }}
                stroke="var(--text-dim)"
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                domain={[0, 1]}
                ticks={[0, 0.25, 0.5, 0.75, 1]}
                tickFormatter={(v: number) => `${Math.round(v * 100)}%`}
                tick={{ fontSize: 10, fontFamily: "var(--font-mono)" }}
                stroke="var(--text-dim)"
                tickLine={false}
                axisLine={false}
                width={36}
              />
              <Tooltip
                contentStyle={{
                  background: "var(--surface)",
                  border: "1px solid var(--border)",
                  borderRadius: 4,
                  fontSize: 11,
                  fontFamily: "var(--font-mono)",
                }}
                formatter={(value) => [fmt(Number(value)), "Score"]}
              />
              {baseline !== null && (
                <ReferenceLine
                  y={baseline}
                  stroke="var(--text-dim)"
                  strokeDasharray="6 4"
                  strokeWidth={1.5}
                />
              )}
              {hasData && (
                <Line
                  type="linear"
                  dataKey="score"
                  stroke="var(--foreground)"
                  strokeWidth={1.5}
                  dot={{
                    r: 3,
                    fill: "var(--surface)",
                    stroke: "var(--foreground)",
                    strokeWidth: 1.5,
                  }}
                  activeDot={{ r: 5 }}
                />
              )}
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Footer — full env path */}
      <div className="border-t border-border-custom px-3 py-1">
        <p className="font-mono text-[10px] text-text-dim">{env}</p>
      </div>
    </div>
  );
}

const POSITIONS = ["top-left", "top-right", "bottom-left", "bottom-right"] as const;

export default function EvalsPage() {
  const [data, setData] = useState<EvalsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const load = async () => {
      try {
        const res = await fetchEvals();
        if (active) {
          setData(res);
          setError(null);
        }
      } catch (err) {
        if (active) setError(err instanceof Error ? err.message : "Failed to load evals");
      }
    };
    load();
    const interval = setInterval(load, 10_000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, []);

  const environments = data?.environments ?? [
    "primeintellect/aime2026",
    "primeintellect/gsm8k",
    "primeintellect/wordle",
    "prime/tau2-synth",
  ];

  return (
    <div className="flex h-screen flex-col bg-background text-foreground">
      <Header />

      {/* Context bar — explains what this page shows */}
      <div className="flex items-center justify-between border-b border-border-custom px-4 py-2">
        <div>
          <span className="font-mono text-[11px] text-foreground">
            Model Performance
          </span>
          <span className="ml-3 font-mono text-[10px] text-text-dim">
            Eval scores across training iterations
          </span>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5">
            <div className="h-px w-4 bg-foreground" />
            <span className="font-mono text-[10px] text-text-dim">
              fine-tuned
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="h-px w-4 border-t border-dashed border-text-dim" />
            <span className="font-mono text-[10px] text-text-dim">
              base model
            </span>
          </div>
        </div>
      </div>

      {error && (
        <div className="border-b border-not-funny/20 bg-not-funny/5 px-4 py-1.5 font-mono text-[11px] text-not-funny">
          {error}
        </div>
      )}

      {/* 2x2 grid filling the viewport */}
      <div className="grid min-h-0 flex-1 grid-cols-2 grid-rows-2">
        {environments.map((env, i) => {
          const baseline = data?.baseline?.[env] ?? null;
          const runs = data?.runs ?? [];
          const chartData = runs
            .filter((r) => r.scores[env] !== undefined)
            .map((r) => ({
              version: `v${r.model_version}`,
              score: r.scores[env],
              timestamp: r.timestamp,
              adapter: r.adapter_id,
            }));

          return (
            <EvalChart
              key={env}
              env={env}
              baseline={baseline}
              chartData={chartData}
              hasData={chartData.length > 0}
              position={POSITIONS[i]}
            />
          );
        })}
      </div>
    </div>
  );
}
