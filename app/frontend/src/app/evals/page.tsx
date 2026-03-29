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

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-5xl">
          <div className="mb-6">
            <h2 className="text-lg font-semibold tracking-tight">
              Model Performance
            </h2>
            <p className="font-mono text-xs text-text-dim">
              Eval scores across training iterations. Dotted line = base model.
            </p>
          </div>

          {error && (
            <div className="mb-4 rounded border border-not-funny/20 bg-not-funny/5 px-4 py-2 font-mono text-xs text-not-funny">
              {error}
            </div>
          )}

          <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
            {environments.map((env) => {
              const baseline = data?.baseline?.[env] ?? null;
              const runs = data?.runs ?? [];

              // Build chart data: one point per run that has a score for this env
              const chartData = runs
                .filter((r) => r.scores[env] !== undefined)
                .map((r) => ({
                  version: `v${r.model_version}`,
                  score: r.scores[env],
                  timestamp: r.timestamp,
                  adapter: r.adapter_id,
                }));

              const hasData = chartData.length > 0;

              return (
                <div
                  key={env}
                  className="rounded-lg border border-border-custom bg-surface p-4"
                >
                  <div className="mb-3 flex items-baseline justify-between">
                    <h3 className="font-mono text-sm font-medium">
                      {envLabel(env)}
                    </h3>
                    {baseline !== null && (
                      <span className="font-mono text-[10px] text-text-dim">
                        baseline: {fmt(baseline)}
                      </span>
                    )}
                  </div>

                  {!hasData && baseline === null ? (
                    <div className="flex h-48 items-center justify-center font-mono text-xs text-text-dim">
                      No eval data yet. Submit results via POST /evals.
                    </div>
                  ) : (
                    <ResponsiveContainer width="100%" height={200}>
                      <LineChart
                        data={
                          hasData
                            ? chartData
                            : [{ version: "base", score: baseline ?? 0, timestamp: "", adapter: null }]
                        }
                        margin={{ top: 5, right: 10, left: 10, bottom: 5 }}
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
                        />
                        <YAxis
                          domain={[0, 1]}
                          ticks={[0, 0.25, 0.5, 0.75, 1]}
                          tickFormatter={(v: number) => `${Math.round(v * 100)}%`}
                          tick={{ fontSize: 10, fontFamily: "var(--font-mono)" }}
                          stroke="var(--text-dim)"
                          tickLine={false}
                          width={40}
                        />
                        <Tooltip
                          contentStyle={{
                            background: "var(--surface)",
                            border: "1px solid var(--border)",
                            borderRadius: 6,
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
                            label={{
                              value: "base",
                              position: "right",
                              fontSize: 10,
                              fill: "var(--text-dim)",
                              fontFamily: "var(--font-mono)",
                            }}
                          />
                        )}
                        {hasData && (
                          <Line
                            type="linear"
                            dataKey="score"
                            stroke="var(--foreground)"
                            strokeWidth={2}
                            dot={{
                              r: 4,
                              fill: "var(--surface)",
                              stroke: "var(--foreground)",
                              strokeWidth: 2,
                            }}
                            activeDot={{ r: 6 }}
                          />
                        )}
                      </LineChart>
                    </ResponsiveContainer>
                  )}

                  <p className="mt-2 font-mono text-[10px] text-text-dim">
                    {env}
                  </p>
                </div>
              );
            })}
          </div>

          {/* Legend */}
          <div className="mt-6 flex items-center gap-6 font-mono text-[11px] text-text-dim">
            <div className="flex items-center gap-2">
              <div className="h-0.5 w-6 bg-foreground" />
              <span>Fine-tuned model</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="h-0.5 w-6 border-t-2 border-dashed border-text-dim" />
              <span>Base model (Qwen3-4B)</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
