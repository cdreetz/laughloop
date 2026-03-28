"use client";

import { useEffect, useState } from "react";
import { fetchPipeline, type PipelineResponse } from "@/lib/api";

interface PipelinePanelProps {
  refreshKey: number;
}

function ProgressBar({
  value,
  max,
  color = "bg-accent",
}: {
  value: number;
  max: number;
  color?: string;
}) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-background">
      <div
        className={`h-full rounded-full transition-all duration-500 ${color}`}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

function PipelineStage({
  label,
  active,
  completed,
  children,
}: {
  label: string;
  active: boolean;
  completed: boolean;
  children: React.ReactNode;
}) {
  return (
    <div
      className={`rounded-lg border p-3 transition-all ${
        active
          ? "border-accent bg-accent-glow"
          : completed
            ? "border-funny/30 bg-funny-glow/30"
            : "border-border-custom bg-surface"
      }`}
    >
      <div className="mb-2 flex items-center gap-2">
        <div
          className={`h-2.5 w-2.5 rounded-full ${
            active
              ? "bg-accent animate-pulse"
              : completed
                ? "bg-funny"
                : "bg-border-custom"
          }`}
        />
        <span className="font-mono text-[11px] font-semibold uppercase tracking-wider text-text-dim">
          {label}
        </span>
      </div>
      {children}
    </div>
  );
}

export function PipelinePanel({ refreshKey }: PipelinePanelProps) {
  const [pipeline, setPipeline] = useState<PipelineResponse | null>(null);

  useEffect(() => {
    let active = true;
    const load = async () => {
      try {
        const data = await fetchPipeline();
        if (active) setPipeline(data);
      } catch {
        // Non-critical
      }
    };
    load();
    const interval = setInterval(load, 5000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, [refreshKey]);

  if (!pipeline) return null;

  const { data_collection, batch_queue, training, model } = pipeline;
  const isTraining = training.status !== "idle";

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-border-custom px-3 py-2">
        <div className="flex items-center gap-2">
          <div
            className={`h-2 w-2 rounded-full ${
              isTraining ? "bg-accent animate-pulse" : "bg-text-dim"
            }`}
          />
          <h3 className="font-mono text-xs font-semibold uppercase tracking-wider text-text-dim">
            Training Pipeline
          </h3>
        </div>
        <div className="flex items-center gap-1.5 rounded-full border border-border-custom bg-surface px-2.5 py-1">
          <span className="font-mono text-[10px] text-text-dim">model</span>
          <span
            className={`font-mono text-[11px] font-bold ${
              model.version > 0 ? "text-funny" : "text-accent"
            }`}
          >
            {model.version_display}
          </span>
        </div>
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto p-3">
        {/* Stage 1: Data Collection */}
        <PipelineStage
          label="1. Collect Feedback"
          active={!isTraining}
          completed={batch_queue.ready_for_export}
        >
          <div className="space-y-1.5">
            <div className="flex justify-between font-mono text-[11px]">
              <span className="text-text-dim">
                {data_collection.unexported} / {batch_queue.min_batch_size}{" "}
                labeled
              </span>
              <span
                className={
                  batch_queue.ready_for_export ? "text-funny" : "text-accent"
                }
              >
                {batch_queue.ready_for_export ? "Ready!" : "Collecting..."}
              </span>
            </div>
            <ProgressBar
              value={data_collection.unexported}
              max={batch_queue.min_batch_size}
              color={batch_queue.ready_for_export ? "bg-funny" : "bg-accent"}
            />
            <div className="flex gap-3 font-mono text-[10px] text-text-dim">
              <span>{data_collection.total_interactions} total</span>
              <span>{data_collection.labeled} labeled</span>
              <span>{data_collection.exported} exported</span>
            </div>
          </div>
        </PipelineStage>

        {/* Arrow connector */}
        <div className="flex justify-center">
          <div className="font-mono text-xs text-text-dim">
            {"\u2193"}
          </div>
        </div>

        {/* Stage 2: Batch Export */}
        <PipelineStage
          label="2. Export Training Batch"
          active={training.status === "exporting"}
          completed={batch_queue.batches.length > 0}
        >
          <div className="space-y-1.5">
            {batch_queue.batches.length > 0 ? (
              <div className="space-y-1">
                {batch_queue.batches.slice(0, 3).map((batch) => (
                  <div
                    key={batch.filename}
                    className="flex items-center justify-between rounded border border-border-custom bg-background px-2 py-1"
                  >
                    <span className="truncate font-mono text-[10px] text-foreground">
                      {batch.filename}
                    </span>
                    <span className="ml-2 shrink-0 font-mono text-[10px] text-text-dim">
                      {batch.records} records
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="font-mono text-[10px] text-text-dim">
                No batches exported yet
              </p>
            )}
          </div>
        </PipelineStage>

        {/* Arrow connector */}
        <div className="flex justify-center">
          <div className="font-mono text-xs text-text-dim">
            {"\u2193"}
          </div>
        </div>

        {/* Stage 3: RL Training */}
        <PipelineStage
          label="3. RL Training (Prime)"
          active={training.status === "training"}
          completed={training.batches_completed > 0}
        >
          <div className="space-y-1.5">
            <div className="flex justify-between font-mono text-[11px]">
              <span className="text-text-dim">
                {training.batches_completed} runs completed
              </span>
              <span
                className={
                  training.status === "training"
                    ? "text-accent animate-pulse"
                    : "text-text-dim"
                }
              >
                {training.status === "training"
                  ? "Training..."
                  : training.status === "idle"
                    ? "Waiting"
                    : training.status}
              </span>
            </div>
            {training.last_training_time && (
              <p className="font-mono text-[10px] text-text-dim">
                Last run: {new Date(training.last_training_time).toLocaleString()}
              </p>
            )}
          </div>
        </PipelineStage>

        {/* Arrow connector */}
        <div className="flex justify-center">
          <div className="font-mono text-xs text-text-dim">
            {"\u2193"}
          </div>
        </div>

        {/* Stage 4: Model Deployment */}
        <PipelineStage
          label="4. Deploy Adapter"
          active={training.status === "deploying"}
          completed={model.version > 0}
        >
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="font-mono text-[11px] text-text-dim">
                Active model:
              </span>
              <span
                className={`font-mono text-sm font-bold ${
                  model.version > 0 ? "text-funny" : "text-accent"
                }`}
              >
                {model.name.split("/").pop()} {model.version_display}
              </span>
            </div>
            {model.adapter_id && (
              <p className="font-mono text-[10px] text-text-dim">
                LoRA: {model.adapter_id}
              </p>
            )}
            {model.adapter_history.length > 0 && (
              <div className="space-y-0.5">
                {model.adapter_history.map((h, i) => (
                  <div
                    key={i}
                    className="font-mono text-[10px] text-text-dim"
                  >
                    v{h.version}: {h.adapter_id.slice(0, 12)}... ({h.batch_size}{" "}
                    samples)
                  </div>
                ))}
              </div>
            )}
          </div>
        </PipelineStage>
      </div>
    </div>
  );
}
