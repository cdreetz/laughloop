"""
LaughLoop Backend — FastAPI server for chat + feedback collection.

Endpoints:
  POST /chat         — Send a message, get a funny response
  POST /feedback     — Record whether a response was funny (haha or not)
  GET  /stats        — Get current feedback statistics
  GET  /health       — Health check (includes current model info)
"""

import json
import os
import sqlite3
import time
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

DB_PATH = Path(__file__).parent / "laughloop.db"

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
# Database
# ---------------------------------------------------------------------------


def init_db():
    """Initialize SQLite database for interaction logging."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS interactions (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            user_message TEXT NOT NULL,
            assistant_message TEXT NOT NULL,
            model TEXT NOT NULL,
            adapter_id TEXT DEFAULT '',
            feedback INTEGER DEFAULT NULL,
            feedback_timestamp TEXT DEFAULT NULL,
            exported INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_interactions_exported
        ON interactions(exported)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_interactions_session
        ON interactions(session_id)
    """)
    conn.commit()
    conn.close()


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


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
    init_db()
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
    db = get_db()
    rows = db.execute(
        "SELECT user_message, assistant_message FROM interactions "
        "WHERE session_id = ? ORDER BY timestamp DESC LIMIT 10",
        (session_id,),
    ).fetchall()
    db.close()

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for row in reversed(rows):
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

    # Log to database
    db = get_db()
    db.execute(
        "INSERT INTO interactions (id, session_id, timestamp, user_message, "
        "assistant_message, model, adapter_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            interaction_id,
            session_id,
            datetime.now(timezone.utc).isoformat(),
            req.message,
            assistant_message,
            MODEL_NAME,
            ADAPTER_ID,
        ),
    )
    db.commit()
    db.close()

    return ChatResponse(
        id=interaction_id,
        response=assistant_message,
        session_id=session_id,
    )


@app.post("/feedback", response_model=FeedbackResponse)
async def feedback(req: FeedbackRequest):
    """Record user feedback (funny or not) for an interaction."""
    db = get_db()
    row = db.execute(
        "SELECT id FROM interactions WHERE id = ?", (req.interaction_id,)
    ).fetchone()

    if not row:
        db.close()
        raise HTTPException(status_code=404, detail="Interaction not found")

    db.execute(
        "UPDATE interactions SET feedback = ?, feedback_timestamp = ? WHERE id = ?",
        (1 if req.funny else 0, datetime.now(timezone.utc).isoformat(), req.interaction_id),
    )
    db.commit()
    db.close()

    return FeedbackResponse(success=True)


@app.get("/stats", response_model=StatsResponse)
async def stats():
    """Get current feedback statistics."""
    db = get_db()
    total = db.execute("SELECT COUNT(*) FROM interactions").fetchone()[0]
    with_feedback = db.execute(
        "SELECT COUNT(*) FROM interactions WHERE feedback IS NOT NULL"
    ).fetchone()[0]
    funny = db.execute(
        "SELECT COUNT(*) FROM interactions WHERE feedback = 1"
    ).fetchone()[0]
    not_funny = db.execute(
        "SELECT COUNT(*) FROM interactions WHERE feedback = 0"
    ).fetchone()[0]
    unexported = db.execute(
        "SELECT COUNT(*) FROM interactions WHERE exported = 0 AND feedback IS NOT NULL"
    ).fetchone()[0]
    db.close()

    haha_rate = funny / with_feedback if with_feedback > 0 else 0.0

    return StatsResponse(
        total_interactions=total,
        total_feedback=with_feedback,
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
        "db_path": str(DB_PATH),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
