"""
LaughLoop Backend — FastAPI server for chat + feedback collection.

Uses append-only JSONL log files instead of SQLite for object-store compatibility.

Endpoints:
  POST /chat         — Send a message, get a funny response
  POST /feedback     — Record whether a response was funny (haha or not)
  GET  /stats        — Get current feedback statistics
  GET  /health       — Health check (includes current model info)
"""

import json
import os
import threading
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai import AsyncOpenAI
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MODEL_NAME = os.getenv("LAUGHLOOP_MODEL", "openai/gpt-4.1-mini")
BASE_URL = os.getenv("LAUGHLOOP_BASE_URL", "https://api.pinference.ai/api/v1")
API_KEY = os.getenv("LAUGHLOOP_API_KEY") or os.getenv("PRIME_API_KEY", "")
ADAPTER_ID = os.getenv("LAUGHLOOP_ADAPTER_ID", "")  # set after first training run
TEAM_ID = os.getenv("PRIME_TEAM_ID", "")  # required for team accounts on Prime

LOG_DIR = Path(os.getenv("LAUGHLOOP_LOG_DIR", str(Path(__file__).parent / "logs")))
INTERACTIONS_LOG = LOG_DIR / "interactions.jsonl"

SYSTEM_PROMPT = """You are LaughLoop, a hilariously witty AI assistant. Your #1 goal is to make the user laugh.

Rules:
- Every response should try to be genuinely funny — use wordplay, unexpected twists, absurd comparisons, self-deprecation, observational humor, or whatever lands best.
- Stay helpful — if someone asks a real question, answer it AND make it funny.
- Keep responses concise. The best jokes don't need paragraphs.
- Vary your humor style. Don't repeat the same schtick.
- Never be mean-spirited or punch down. Humor should be inclusive.
- If a joke doesn't land, pivot — don't double down on the same bit.

You're performing live. Every message is a chance to get a laugh. Make it count."""


# ---------------------------------------------------------------------------
# JSONL Log Storage
# ---------------------------------------------------------------------------

# Thread lock for safe appends from concurrent requests
_log_lock = threading.Lock()


def _append_log(record: dict):
    """Append a single JSON record to the interactions log."""
    with _log_lock:
        with open(INTERACTIONS_LOG, "a") as f:
            f.write(json.dumps(record, default=str) + "\n")


def _read_all_interactions() -> list[dict]:
    """Read all interaction records from the log file."""
    if not INTERACTIONS_LOG.exists():
        return []
    records = []
    with open(INTERACTIONS_LOG) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return records


def _rewrite_log(records: list[dict]):
    """Rewrite the entire log file (used for updates like feedback)."""
    with _log_lock:
        with open(INTERACTIONS_LOG, "w") as f:
            for record in records:
                f.write(json.dumps(record, default=str) + "\n")


def _get_session_history(session_id: str, limit: int = 10) -> list[dict]:
    """Get the last N interactions for a session."""
    all_records = _read_all_interactions()
    session_records = [r for r in all_records if r.get("session_id") == session_id]
    return session_records[-limit:]


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    id: str
    response: str
    session_id: str


class FeedbackRequest(BaseModel):
    interaction_id: str
    funny: bool  # True = 😂 Haha, False = no reaction / explicit not-funny


class FeedbackResponse(BaseModel):
    success: bool


class StatsResponse(BaseModel):
    total_interactions: int
    total_feedback: int
    funny_count: int
    not_funny_count: int
    haha_rate: float
    unexported_count: int
    current_model: str
    current_adapter: str


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="LaughLoop", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_default_headers = {}
if TEAM_ID:
    _default_headers["X-Prime-Team-ID"] = TEAM_ID

client = AsyncOpenAI(
    base_url=BASE_URL,
    api_key=API_KEY,
    default_headers=_default_headers if _default_headers else None,
)


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Generate a funny response and log the interaction."""
    session_id = req.session_id or str(uuid.uuid4())
    interaction_id = str(uuid.uuid4())

    # Load conversation history for this session (last 10 turns)
    history = _get_session_history(session_id, limit=10)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for row in history:
        messages.append({"role": "user", "content": row["user_message"]})
        messages.append({"role": "assistant", "content": row["assistant_message"]})
    messages.append({"role": "user", "content": req.message})

    # Call the model
    try:
        extra_body = {}
        if ADAPTER_ID:
            extra_body["lora_id"] = ADAPTER_ID

        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            max_tokens=512,
            temperature=0.9,
            extra_body=extra_body if extra_body else None,
        )
        assistant_message = response.choices[0].message.content or "(crickets)"
    except Exception as e:
        # Fallback: still log the attempt
        assistant_message = f"My comedy circuits are overloaded right now. (Error: {e})"

    # Log to JSONL file
    record = {
        "id": interaction_id,
        "session_id": session_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_message": req.message,
        "assistant_message": assistant_message,
        "model": MODEL_NAME,
        "adapter_id": ADAPTER_ID,
        "feedback": None,
        "feedback_timestamp": None,
        "exported": 0,
    }
    _append_log(record)

    return ChatResponse(
        id=interaction_id,
        response=assistant_message,
        session_id=session_id,
    )


@app.post("/feedback", response_model=FeedbackResponse)
async def feedback(req: FeedbackRequest):
    """Record user feedback (funny or not) for an interaction."""
    records = _read_all_interactions()

    found = False
    for record in records:
        if record.get("id") == req.interaction_id:
            record["feedback"] = 1 if req.funny else 0
            record["feedback_timestamp"] = datetime.now(timezone.utc).isoformat()
            found = True
            break

    if not found:
        raise HTTPException(status_code=404, detail="Interaction not found")

    _rewrite_log(records)
    return FeedbackResponse(success=True)


@app.get("/stats", response_model=StatsResponse)
async def stats():
    """Get current feedback statistics."""
    records = _read_all_interactions()

    total = len(records)
    with_feedback = [r for r in records if r.get("feedback") is not None]
    funny = sum(1 for r in with_feedback if r["feedback"] == 1)
    not_funny = sum(1 for r in with_feedback if r["feedback"] == 0)
    unexported = sum(
        1 for r in records
        if r.get("exported", 0) == 0 and r.get("feedback") is not None
    )

    haha_rate = funny / len(with_feedback) if with_feedback else 0.0

    return StatsResponse(
        total_interactions=total,
        total_feedback=len(with_feedback),
        funny_count=funny,
        not_funny_count=not_funny,
        haha_rate=round(haha_rate, 4),
        unexported_count=unexported,
        current_model=MODEL_NAME,
        current_adapter=ADAPTER_ID or "(base model)",
    )


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "model": MODEL_NAME,
        "adapter": ADAPTER_ID or None,
        "log_dir": str(LOG_DIR),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
