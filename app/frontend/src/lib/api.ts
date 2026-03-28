const API_BASE = "/api";

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
