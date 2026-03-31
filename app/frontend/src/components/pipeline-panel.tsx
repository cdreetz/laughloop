"use client";

import { useEffect, useState } from "react";
import { fetchPipeline, resetPipelineStage, type PipelineResponse } from "@/lib/api";

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

function PulsingDot({ active }: { active: boolean }) {
  if (!active) return null;
  return (
    <span className="relative ml-1.5 inline-flex h-1.5 w-1.5">
      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-foreground opacity-50" />
      <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-foreground" />
    </span>
  );
}

function Spinner() {
  return (
    <span className="inline-block h-3 w-3 animate-spin rounded-full border border-foreground border-t-transparent" />
  );
}

function StageIcon({ status }: { status: "idle" | "active" | "done" }) {
  if (status === "active") return <Spinner />;
  if (status === "done")
    return (
      <span className="inline-flex h-3 w-3 items-center justify-center rounded-full bg-foreground/10 text-[8px] text-foreground">
        ✓
      </span>
    );
  return <span className="inline-block h-3 w-3 rounded-full border border-border-custom" />;
}

function Stage({
  label,
  active,
  done,
  resetButton,
  children,
}: {
  label: string;
  active?: boolean;
  done?: boolean;
  resetButton?: React.ReactNode;
  children: React.ReactNode;
}) {
  const status = active ? "active" : done ? "done" : "idle";
  return (
    <div
      className={`space-y-2 rounded-md border px-3 py-2 ${
        active
          ? "border-foreground/20 bg-foreground/[0.02]"
          : "border-transparent"
      }`}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <StageIcon status={status} />
          <span className="font-mono text-[10px] font-medium uppercase tracking-wider text-text-dim">
            {label}
          </span>
        </div>
        {resetButton}
      </div>
      {children}
    </div>
  );
}

function formatTimeAgo(isoString: string): string {
  const diff = Date.now() - new Date(isoString).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ${mins % 60}m ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function ResetButton({
  stage,
  onReset,
}: {
  stage: "training" | "deployment" | "eval" | "all";
  onReset: () => void;
}) {
  const [confirming, setConfirming] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleClick = async () => {
    if (!confirming) {
      setConfirming(true);
      setTimeout(() => setConfirming(false), 3000);
      return;
    }
    setLoading(true);
    try {
      await resetPipelineStage(stage);
      onReset();
    } catch {
      // ignore
    } finally {
      setLoading(false);
      setConfirming(false);
    }
  };

  return (
    <button
      onClick={handleClick}
      disabled={loading}
      className="font-mono text-[10px] text-text-dim hover:text-foreground transition-colors disabled:opacity-50"
    >
      {loading ? "resetting..." : confirming ? "confirm reset?" : "reset"}
    </button>
  );
}

export function PipelinePanel({ refreshKey }: PipelinePanelProps) {
  const [pipeline, setPipeline] = useState<PipelineResponse | null>(null);

  const refreshNow = async () => {
    try {
      const data = await fetchPipeline();
      setPipeline(data);
    } catch {
      // ignore
    }
  };

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

  const { data_collection, batch_queue, training, model, evals } = pipeline;
  const isExporting = training.status === "exporting";
  const isTraining = training.status === "training";
  const isDeploying = training.status === "deploying";
  const isEvaling = evals?.status === "running";

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-border-custom px-3 py-2">
        <h3 className="font-mono text-[11px] font-medium text-text-dim">
          Training Pipeline
        </h3>
        <div className="flex items-center gap-2">
          <span className="font-mono text-[10px] text-text-dim">
            {model.version_display}
          </span>
          {(isTraining || isDeploying || isExporting) && (
            <ResetButton stage="all" onReset={refreshNow} />
          )}
        </div>
      </div>

      <div className="flex-1 space-y-2 overflow-y-auto p-3">
        {/* Stage 1: Collect Feedback */}
        <Stage
          label="1. Collect Feedback"
        >
          <div className="space-y-1.5">
            <div className="flex justify-between font-mono text-[11px]">
              <span className="text-text-dim">
                {data_collection.unexported} / {batch_queue.min_batch_size}{" "}
                labeled
              </span>
              <span
                className={
                  batch_queue.ready_for_export
                    ? "text-foreground"
                    : "text-text-dim"
                }
              >
                {batch_queue.ready_for_export ? "Ready to export" : "Collecting"}
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

        {/* Stage 2: Export Batch */}
        <Stage label="2. Export Batch" active={isExporting} done={batch_queue.batches.length > 0}>
          {isExporting && (
            <div className="flex items-center gap-2 font-mono text-[11px] text-foreground">
              <Spinner />
              Exporting batch...
            </div>
          )}
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
                    {batch.size_bytes > 0
                      ? `${(batch.size_bytes / 1024).toFixed(0)} KB`
                      : `${batch.records} records`}
                  </span>
                </div>
              ))}
            </div>
          ) : !isExporting ? (
            <p className="font-mono text-[10px] text-text-dim">
              No batches yet
            </p>
          ) : null}
        </Stage>

        {/* Stage 3: RL Training */}
        <Stage label="3. RL Training" active={isTraining} done={training.batches_completed > 0} resetButton={
          isTraining ? <ResetButton stage="training" onReset={refreshNow} /> : undefined
        }>
          <div className="space-y-1.5">
            <div className="flex justify-between font-mono text-[11px]">
              <span className="text-text-dim">
                {training.batches_completed} run
                {training.batches_completed !== 1 ? "s" : ""}
              </span>
              <span
                className={
                  isTraining || isDeploying || isExporting
                    ? "text-foreground"
                    : "text-text-dim"
                }
              >
                {training.status === "training"
                  ? "Training..."
                  : training.status === "deploying"
                    ? "Deploying..."
                    : training.status === "exporting"
                      ? "Exporting..."
                      : training.status === "idle"
                        ? "Idle"
                        : training.status}
              </span>
            </div>

            {/* Training progress bar */}
            {isTraining && training.run_progress && (
              <div className="space-y-1">
                <ProgressBar
                  value={training.run_progress.latest_step}
                  max={training.run_progress.max_steps}
                />
                <div className="flex justify-between font-mono text-[10px] text-text-dim">
                  <span>
                    Step {training.run_progress.latest_step} /{" "}
                    {training.run_progress.max_steps}
                  </span>
                  {training.run_progress.last_updated_at && (
                    <span>
                      {formatTimeAgo(training.run_progress.last_updated_at)}
                    </span>
                  )}
                </div>
              </div>
            )}

            {/* Spinner when training but no progress yet */}
            {isTraining && !training.run_progress && (
              <div className="flex items-center gap-2 font-mono text-[10px] text-text-dim">
                <Spinner />
                Waiting for first step...
              </div>
            )}

            {training.active_run_id && (
              <div className="space-y-0.5">
                <p className="font-mono text-[10px] text-text-dim">
                  Run: {training.active_run_id}
                </p>
                {training.run_status && (
                  <p className="font-mono text-[10px] text-text-dim">
                    Status: {training.run_status}
                  </p>
                )}
              </div>
            )}
            {training.last_training_time && (
              <p className="font-mono text-[10px] text-text-dim">
                Last: {new Date(training.last_training_time).toLocaleString()}
              </p>
            )}
          </div>
        </Stage>

        {/* Stage 4: Deploy Adapter */}
        <Stage label="4. Deploy Adapter" active={isDeploying} done={!!model.adapter_id} resetButton={
          isDeploying ? <ResetButton stage="deployment" onReset={refreshNow} /> : undefined
        }>
          {isDeploying && (
            <div className="flex items-center gap-2 font-mono text-[11px] text-foreground">
              <Spinner />
              Deploying adapter...
            </div>
          )}
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
                    v{h.version}: {h.adapter_id.slice(0, 12)}... (
                    {h.batch_size} samples)
                  </div>
                ))}
              </div>
            )}
          </div>
        </Stage>

        {/* Stage 5: Eval */}
        <Stage
          label="5. Eval"
          active={isEvaling}
          done={evals?.status === "completed"}
          resetButton={
            isEvaling ? <ResetButton stage="eval" onReset={refreshNow} /> : undefined
          }
        >
          {isEvaling && (
            <div className="space-y-1">
              <div className="flex items-center gap-2 font-mono text-[11px] text-foreground">
                <Spinner />
                Running evals...
              </div>
              {Object.keys(evals?.jobs || {}).length > 0 && (
                <div className="space-y-0.5">
                  {Object.entries(evals.jobs).map(([env]) => {
                    const jobStatus = evals.job_statuses?.[env];
                    const done = jobStatus === "COMPLETED";
                    const failed = jobStatus === "FAILED" || jobStatus === "TIMEOUT" || jobStatus === "CANCELLED";
                    return (
                      <div key={env} className="flex items-center gap-1.5 font-mono text-[10px] text-text-dim">
                        {done ? (
                          <span className="inline-flex h-3 w-3 items-center justify-center rounded-full bg-foreground/10 text-[8px] text-foreground">✓</span>
                        ) : failed ? (
                          <span className="inline-flex h-3 w-3 items-center justify-center rounded-full bg-not-funny/10 text-[8px] text-not-funny">✗</span>
                        ) : (
                          <Spinner />
                        )}
                        <span>{env.split("/").pop()}</span>
                        {failed && <span className="text-not-funny">{jobStatus?.toLowerCase()}</span>}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}
          {evals?.status === "completed" && (
            <p className="font-mono text-[10px] text-text-dim">
              Evals complete{evals.model_version !== null && (
                <> ({evals.model_version === 0 ? "baseline" : `v${evals.model_version}`})</>
              )}
            </p>
          )}
          {!evals?.status && (
            <p className="font-mono text-[10px] text-text-dim">
              Waiting for deployment
            </p>
          )}
        </Stage>
      </div>
    </div>
  );
}
