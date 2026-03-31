"use client";

import { useState } from "react";
import { Header } from "@/components/header";
import {
  fetchPipeline,
  resetPipelineStage,
  generateSynthetic,
  triggerExport,
  triggerTrain,
  triggerDeploy,
  triggerEvalRun,
  type PipelineResponse,
} from "@/lib/api";

export default function AdminPage() {
  const [pipeline, setPipeline] = useState<PipelineResponse | null>(null);
  const [syntheticCount, setSyntheticCount] = useState(20);
  const [generating, setGenerating] = useState(false);
  const [generationResult, setGenerationResult] = useState<string | null>(null);
  const [resetting, setResetting] = useState<string | null>(null);
  const [resetResult, setResetResult] = useState<string | null>(null);
  const [triggerLoading, setTriggerLoading] = useState<string | null>(null);
  const [triggerResult, setTriggerResult] = useState<string | null>(null);
  const [evalLoading, setEvalLoading] = useState(false);
  const [evalResult, setEvalResult] = useState<string | null>(null);

  const refreshPipeline = async () => {
    try {
      const data = await fetchPipeline();
      setPipeline(data);
    } catch {
      // ignore
    }
  };

  // Load pipeline on first render
  useState(() => {
    refreshPipeline();
  });

  const handleGenerate = async () => {
    setGenerating(true);
    setGenerationResult(null);
    try {
      const result = await generateSynthetic(syntheticCount);
      setGenerationResult(
        `Generated ${result.generated} interactions${result.errors > 0 ? ` (${result.errors} errors)` : ""}`
      );
      await refreshPipeline();
    } catch (e) {
      setGenerationResult(`Error: ${e}`);
    } finally {
      setGenerating(false);
    }
  };

  const handleTrigger = async (action: "export" | "train" | "deploy") => {
    setTriggerLoading(action);
    setTriggerResult(null);
    try {
      if (action === "export") {
        const result = await triggerExport();
        setTriggerResult(`Exported ${result.records_exported} records`);
      } else if (action === "train") {
        const result = await triggerTrain();
        setTriggerResult(result.success ? `Training started: ${result.run_id}` : `Error: ${result.error}`);
      } else if (action === "deploy") {
        const result = await triggerDeploy();
        setTriggerResult(result.success ? `Deployed: ${result.adapter_id}` : `Error: ${result.error}`);
      }
      await refreshPipeline();
    } catch (e) {
      setTriggerResult(`Error: ${e}`);
    } finally {
      setTriggerLoading(null);
    }
  };

  const handleEvalRun = async (modelVersion: number) => {
    setEvalLoading(true);
    setEvalResult(null);
    try {
      const result = await triggerEvalRun(modelVersion);
      setEvalResult(result.success ? (result.message || "Eval started") : `Error: ${result.error}`);
    } catch (e) {
      setEvalResult(`Error: ${e}`);
    } finally {
      setEvalLoading(false);
    }
  };

  const handleReset = async (stage: "training" | "deployment" | "eval" | "all") => {
    setResetting(stage);
    setResetResult(null);
    try {
      const result = await resetPipelineStage(stage);
      setResetResult(`Reset ${stage} — status: ${result.status}`);
      await refreshPipeline();
    } catch (e) {
      setResetResult(`Error: ${e}`);
    } finally {
      setResetting(null);
    }
  };

  return (
    <div className="flex h-screen flex-col bg-background text-foreground">
      <Header />

      <div className="flex-1 overflow-auto">
        <div className="mx-auto max-w-2xl space-y-6 p-6">
          <div>
            <h2 className="text-sm font-semibold">Admin</h2>
            <p className="mt-1 font-mono text-[11px] text-text-dim">
              Pipeline controls and data generation
            </p>
          </div>

          {/* Pipeline Status */}
          {pipeline && (
            <div className="space-y-2 rounded-md border border-border-custom p-4">
              <h3 className="font-mono text-[11px] font-medium uppercase tracking-wider text-text-dim">
                Pipeline Status
              </h3>
              <div className="grid grid-cols-2 gap-3 font-mono text-[11px]">
                <div>
                  <span className="text-text-dim">Status: </span>
                  <span className="text-foreground">{pipeline.training.status}</span>
                </div>
                <div>
                  <span className="text-text-dim">Model: </span>
                  <span className="text-foreground">{pipeline.model.version_display}</span>
                </div>
                <div>
                  <span className="text-text-dim">Unexported: </span>
                  <span className="text-foreground">{pipeline.data_collection.unexported}</span>
                </div>
                <div>
                  <span className="text-text-dim">Min batch: </span>
                  <span className="text-foreground">{pipeline.batch_queue.min_batch_size}</span>
                </div>
                <div>
                  <span className="text-text-dim">Labeled: </span>
                  <span className="text-foreground">{pipeline.data_collection.labeled}</span>
                </div>
                <div>
                  <span className="text-text-dim">Runs completed: </span>
                  <span className="text-foreground">{pipeline.training.batches_completed}</span>
                </div>
              </div>
              {pipeline.training.active_run_id && (
                <div className="font-mono text-[10px] text-text-dim">
                  Active run: {pipeline.training.active_run_id}
                </div>
              )}
              {pipeline.evals.status && (
                <div className="flex items-center gap-2 pt-1">
                  {pipeline.evals.status === "running" && (
                    <span className="inline-block h-2 w-2 animate-spin rounded-full border border-foreground border-t-transparent" />
                  )}
                  <span className="font-mono text-[10px] text-text-dim">
                    Evals: {pipeline.evals.status}
                    {pipeline.evals.model_version !== null && (
                      <> ({pipeline.evals.model_version === 0 ? "baseline" : `v${pipeline.evals.model_version}`})</>
                    )}
                    {pipeline.evals.status === "running" && (
                      <> — {Object.keys(pipeline.evals.jobs).length} environments</>
                    )}
                  </span>
                </div>
              )}
            </div>
          )}

          {/* Generate Synthetic Data */}
          <div className="space-y-3 rounded-md border border-border-custom p-4">
            <h3 className="font-mono text-[11px] font-medium uppercase tracking-wider text-text-dim">
              Generate Synthetic Data
            </h3>
            <p className="font-mono text-[10px] text-text-dim">
              Creates chat interactions with the current model and assigns random haha/meh feedback.
              Generates unexported labeled data to trigger the training pipeline.
            </p>
            <div className="flex items-center gap-3">
              <label className="font-mono text-[11px] text-text-dim">Count:</label>
              <input
                type="number"
                min={1}
                max={50}
                value={syntheticCount}
                onChange={(e) => setSyntheticCount(Number(e.target.value))}
                className="w-20 rounded border border-border-custom bg-background px-2 py-1 font-mono text-[11px] text-foreground"
              />
              <button
                onClick={handleGenerate}
                disabled={generating}
                className="rounded border border-border-custom px-3 py-1 font-mono text-[11px] text-text-dim transition-colors hover:border-foreground hover:text-foreground disabled:opacity-50"
              >
                {generating ? "Generating..." : "Generate"}
              </button>
            </div>
            {generationResult && (
              <p className="font-mono text-[10px] text-foreground">{generationResult}</p>
            )}
          </div>

          {/* Trigger Pipeline Steps */}
          <div className="space-y-3 rounded-md border border-border-custom p-4">
            <h3 className="font-mono text-[11px] font-medium uppercase tracking-wider text-text-dim">
              Trigger Pipeline
            </h3>
            <p className="font-mono text-[10px] text-text-dim">
              Manually trigger individual pipeline steps.
            </p>
            <div className="flex flex-wrap gap-2">
              {(["export", "train", "deploy"] as const).map((action) => (
                <button
                  key={action}
                  onClick={() => handleTrigger(action)}
                  disabled={triggerLoading !== null}
                  className="rounded border border-border-custom px-3 py-1 font-mono text-[11px] text-text-dim transition-colors hover:border-foreground hover:text-foreground disabled:opacity-50"
                >
                  {triggerLoading === action ? `${action}ing...` : action}
                </button>
              ))}
            </div>
            {triggerResult && (
              <p className="font-mono text-[10px] text-foreground">{triggerResult}</p>
            )}
          </div>

          {/* Run Evals */}
          <div className="space-y-3 rounded-md border border-border-custom p-4">
            <h3 className="font-mono text-[11px] font-medium uppercase tracking-wider text-text-dim">
              Run Evals
            </h3>
            <p className="font-mono text-[10px] text-text-dim">
              Trigger hosted evaluations on Prime. Baseline runs the base model (version 0).
              Results appear on the Evals page.
            </p>
            <div className="flex flex-wrap gap-2">
              <button
                onClick={() => handleEvalRun(0)}
                disabled={evalLoading}
                className="rounded border border-border-custom px-3 py-1 font-mono text-[11px] text-text-dim transition-colors hover:border-foreground hover:text-foreground disabled:opacity-50"
              >
                {evalLoading ? "Running..." : "Run Baseline Eval"}
              </button>
              {pipeline && pipeline.model.version > 0 && (
                <button
                  onClick={() => handleEvalRun(pipeline.model.version)}
                  disabled={evalLoading}
                  className="rounded border border-border-custom px-3 py-1 font-mono text-[11px] text-text-dim transition-colors hover:border-foreground hover:text-foreground disabled:opacity-50"
                >
                  {evalLoading ? "Running..." : `Run v${pipeline.model.version} Eval`}
                </button>
              )}
            </div>
            {evalResult && (
              <p className="font-mono text-[10px] text-foreground">{evalResult}</p>
            )}
          </div>

          {/* Reset Pipeline */}
          <div className="space-y-3 rounded-md border border-border-custom p-4">
            <h3 className="font-mono text-[11px] font-medium uppercase tracking-wider text-text-dim">
              Reset Pipeline
            </h3>
            <p className="font-mono text-[10px] text-text-dim">
              Reset stuck pipeline stages back to idle. Use when a step gets stuck or you want to start fresh.
            </p>
            <div className="flex flex-wrap gap-2">
              {(["training", "deployment", "eval", "all"] as const).map((stage) => (
                <button
                  key={stage}
                  onClick={() => handleReset(stage)}
                  disabled={resetting !== null}
                  className="rounded border border-border-custom px-3 py-1 font-mono text-[11px] text-text-dim transition-colors hover:border-foreground hover:text-foreground disabled:opacity-50"
                >
                  {resetting === stage ? "Resetting..." : `Reset ${stage}`}
                </button>
              ))}
            </div>
            {resetResult && (
              <p className="font-mono text-[10px] text-foreground">{resetResult}</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
