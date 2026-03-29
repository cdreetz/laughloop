const API_BASE = process.env.NEXT_PUBLIC_API_URL || "/api";

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
