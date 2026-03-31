const API_BASE = (process.env.NEXT_PUBLIC_API_URL || "/api").replace(/\/+$/, "");

export interface ChatResponse {
  id: string;
  session_id: string;
  response: string;
}

export interface FeedbackPayload {
  interaction_id: string;
  funny: boolean;
}

export interface Stats {
  total_interactions: number;
  funny_count: number;
  not_funny_count: number;
  pending_count: number;
  haha_rate: number;
  current_adapter: string;
}

export interface Interaction {
  id: string;
  session_id: string;
  timestamp: string;
  user_message: string;
  assistant_message: string;
  model: string;
  adapter_id: string;
  feedback: number | null;
  feedback_timestamp: string | null;
  exported: number;
}

export interface InteractionsResponse {
  total: number;
  offset: number;
  limit: number;
  interactions: Interaction[];
}

export interface BatchInfo {
  filename: string;
  records: number;
  created_at: string;
  size_bytes: number;
}

export interface PipelineResponse {
  data_collection: {
    total_interactions: number;
    labeled: number;
    unlabeled: number;
    unexported: number;
    exported: number;
  };
  batch_queue: {
    pending_for_export: number;
    min_batch_size: number;
    ready_for_export: boolean;
    batches: BatchInfo[];
  };
  training: {
    status: "idle" | "exporting" | "training" | "deploying";
    current_batch: string | null;
    batches_completed: number;
    last_training_time: string | null;
    active_run_id: string | null;
    run_status: string | null;
    run_progress: {
      latest_step: number;
      max_steps: number;
      last_updated_at: string | null;
    } | null;
  };
  model: {
    name: string;
    version: number;
    version_display: string;
    adapter_id: string | null;
    adapter_history: Array<{
      version: number;
      adapter_id: string;
      timestamp: string;
      batch_size: number;
    }>;
  };
  evals: {
    status: string | null;
    jobs: Record<string, string>;
    job_statuses: Record<string, string>;
    model_version: number | null;
  };
}

export async function sendChat(message: string, sessionId: string | null): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, session_id: sessionId }),
  });
  if (!res.ok) throw new Error(`Chat failed: ${res.status}`);
  return res.json();
}

export async function sendFeedback(payload: FeedbackPayload): Promise<void> {
  await fetch(`${API_BASE}/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function fetchStats(): Promise<Stats> {
  const res = await fetch(`${API_BASE}/stats`);
  if (!res.ok) throw new Error(`Stats failed: ${res.status}`);
  return res.json();
}

export async function fetchInteractions(limit = 50, offset = 0): Promise<InteractionsResponse> {
  const res = await fetch(`${API_BASE}/interactions?limit=${limit}&offset=${offset}`);
  if (!res.ok) throw new Error(`Interactions failed: ${res.status}`);
  return res.json();
}

export async function fetchPipeline(): Promise<PipelineResponse> {
  const res = await fetch(`${API_BASE}/pipeline`);
  if (!res.ok) throw new Error(`Pipeline failed: ${res.status}`);
  return res.json();
}

export interface EvalRun {
  model_version: number;
  adapter_id: string | null;
  scores: Record<string, number>;
  timestamp: string;
}

export interface EvalsResponse {
  environments: string[];
  baseline: Record<string, number>;
  runs: EvalRun[];
}

export async function resetPipelineStage(stage: "training" | "deployment" | "eval" | "all"): Promise<{ success: boolean; stage: string; status: string }> {
  const res = await fetch(`${API_BASE}/pipeline/reset`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ stage }),
  });
  if (!res.ok) throw new Error(`Reset failed: ${res.status}`);
  return res.json();
}

export async function triggerExport(): Promise<{ success: boolean; records_exported: number; batch_file: string | null }> {
  const res = await fetch(`${API_BASE}/pipeline/export`, { method: "POST" });
  if (!res.ok) throw new Error(`Export failed: ${res.status}`);
  return res.json();
}

export async function triggerTrain(): Promise<{ success: boolean; run_id?: string; error?: string }> {
  const res = await fetch(`${API_BASE}/pipeline/train`, { method: "POST" });
  if (!res.ok) throw new Error(`Train failed: ${res.status}`);
  return res.json();
}

export async function triggerDeploy(runId?: string): Promise<{ success: boolean; adapter_id?: string; error?: string }> {
  const res = await fetch(`${API_BASE}/pipeline/deploy`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(runId ? { run_id: runId } : {}),
  });
  if (!res.ok) throw new Error(`Deploy failed: ${res.status}`);
  return res.json();
}

export async function triggerEvalRun(modelVersion: number = 0): Promise<{ success: boolean; mode?: string; message?: string; error?: string }> {
  const res = await fetch(`${API_BASE}/evals/run?model_version=${modelVersion}`, { method: "POST" });
  if (!res.ok) throw new Error(`Eval run failed: ${res.status}`);
  return res.json();
}

export async function generateSynthetic(count: number = 20): Promise<{ success: boolean; generated: number; errors: number }> {
  const res = await fetch(`${API_BASE}/admin/generate-synthetic`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ count }),
  });
  if (!res.ok) throw new Error(`Synthetic generation failed: ${res.status}`);
  return res.json();
}

export async function fetchEvals(): Promise<EvalsResponse> {
  const res = await fetch(`${API_BASE}/evals`);
  if (!res.ok) throw new Error(`Evals failed: ${res.status}`);
  return res.json();
}
