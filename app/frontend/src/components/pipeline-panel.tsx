"use client";

import { useEffect, useState } from "react";
import { fetchPipeline, type PipelineResponse } from "@/lib/api";

interface PipelinePanelProps {
  refreshKey: number;
}

function ProgressBar({ value, max }: { value: number; max: number }) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;
  return (
    <div className="h-1 w-full overflow-hidden rounded-full bg-border-custom">
      <div
        className="h-full rounded-full bg-foreground transition-all duration-500"
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

function Stage({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-2">
      <span className="font-mono text-[10px] font-medium uppercase tracking-wider text-text-dim">
        {label}
      </span>
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
        <h3 className="font-mono text-[11px] font-medium text-text-dim">
          Training Pipeline
        </h3>
        <span className="font-mono text-[10px] text-text-dim">
          {model.version_display}
        </span>
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto p-3">
        <Stage label="1. Collect Feedback">
          <div className="space-y-1.5">
            <div className="flex justify-between font-mono text-[11px]">
              <span className="text-text-dim">
                {data_collection.unexported} / {batch_queue.min_batch_size} labeled
              </span>
              <span className="text-text-dim">
                {batch_queue.ready_for_export ? "Ready" : "Collecting"}
              </span>
            </div>
            <ProgressBar
              value={data_collection.unexported}
              max={batch_queue.min_batch_size}
            />
            <div className="flex gap-3 font-mono text-[10px] text-text-dim">
              <span>{data_collection.total_interactions} total</span>
              <span>{data_collection.labeled} labeled</span>
              <span>{data_collection.exported} exported</span>
            </div>
          </div>
        </Stage>

        <Stage label="2. Export Batch">
          {batch_queue.batches.length > 0 ? (
            <div className="space-y-1">
              {batch_queue.batches.slice(0, 3).map((batch) => (
                <div
                  key={batch.filename}
                  className="flex items-center justify-between font-mono text-[10px]"
                >
                  <span className="truncate text-foreground">
                    {batch.filename}
                  </span>
                  <span className="ml-2 shrink-0 text-text-dim">
                    {batch.records} records
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="font-mono text-[10px] text-text-dim">
              No batches yet
            </p>
          )}
        </Stage>

        <Stage label="3. RL Training">
          <div className="space-y-1">
            <div className="flex justify-between font-mono text-[11px]">
              <span className="text-text-dim">
                {training.batches_completed} runs
              </span>
              <span
                className={
                  isTraining
                    ? "text-foreground"
                    : "text-text-dim"
                }
              >
                {training.status === "training"
                  ? "Training..."
                  : training.status === "idle"
                    ? "Idle"
                    : training.status}
              </span>
            </div>
            {training.last_training_time && (
              <p className="font-mono text-[10px] text-text-dim">
                Last: {new Date(training.last_training_time).toLocaleString()}
              </p>
            )}
          </div>
        </Stage>

        <Stage label="4. Deploy Adapter">
          <div className="space-y-1">
            <div className="flex items-center justify-between font-mono text-[11px]">
              <span className="text-text-dim">Active:</span>
              <span className="text-foreground">
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
                    v{h.version}: {h.adapter_id.slice(0, 12)}... ({h.batch_size} samples)
                  </div>
                ))}
              </div>
            )}
          </div>
        </Stage>
      </div>
    </div>
  );
}
