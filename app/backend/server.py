"""
LaughLoop Backend — FastAPI server for chat + feedback collection.

Uses append-only JSONL log files instead of SQLite for object-store compatibility.

Endpoints:
  POST /chat             — Send a message, get a funny response
  POST /feedback         — Record whether a response was funny (haha or not)
  GET  /stats            — Get current feedback statistics
  GET  /interactions     — Get all interaction log entries (for log viewer)
  GET  /pipeline         — Get training pipeline status (batches, training, model version)
  POST /pipeline/export  — Trigger batch export from interaction logs
  POST /pipeline/train   — Start an RL training run on Prime
  POST /pipeline/deploy  — Deploy the latest adapter from a completed run
  GET  /health           — Health check (includes current model info)
"""

import asyncio
import json
import logging
import os
import threading
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from openai import AsyncOpenAI
from pydantic import BaseModel

# Optional R2/S3 support — only imported when R2 env vars are set
try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    boto3 = None  # type: ignore[assignment]
    ClientError = Exception  # type: ignore[assignment,misc]

logger = logging.getLogger("laughloop")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MODEL_NAME = os.getenv("LAUGHLOOP_MODEL", "Qwen/Qwen3-4B-Instruct-2507")
BASE_URL = os.getenv("LAUGHLOOP_BASE_URL", "https://api.pinference.ai/api/v1")
API_KEY = os.getenv("LAUGHLOOP_API_KEY") or os.getenv("PRIME_API_KEY", "")
ADAPTER_ID = os.getenv("LAUGHLOOP_ADAPTER_ID", "")  # set after first training run
TEAM_ID = os.getenv("PRIME_TEAM_ID", "")  # required for team accounts on Prime
PRIME_BASE_URL = os.getenv("PRIME_BASE_URL", "https://api.primeintellect.ai")
PROJECT_ROOT = Path(__file__).parent.parent.parent

LOG_DIR = Path(os.getenv("LAUGHLOOP_LOG_DIR", str(Path(__file__).parent / "logs")))
INTERACTIONS_LOG = LOG_DIR / "interactions.jsonl"
BATCH_DIR = Path(os.getenv("LAUGHLOOP_BATCH_DIR", str(Path(__file__).parent.parent.parent / "data" / "batches")))

# R2 / S3-compatible object store config
R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID", "")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID", "")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY", "")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME", "laughloop")
R2_LOG_KEY = os.getenv("R2_LOG_KEY", "logs/interactions.jsonl")

USE_R2 = bool(R2_ACCOUNT_ID and R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY and boto3)

_s3_client = None
if USE_R2:
    _s3_client = boto3.client(
        "s3",
        endpoint_url=f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )

# Training pipeline state — persisted to R2 when available so it survives
# serverless cold starts (Vercel).  Falls back to in-memory for local dev.
R2_STATE_KEY = os.getenv("R2_STATE_KEY", "pipeline/state.json")

_DEFAULT_TRAINING_STATE: dict[str, Any] = {
    "status": "idle",  # idle | exporting | training | deploying
    "current_batch": None,
    "batches_completed": 0,
    "last_training_time": None,
    "model_version": 0,  # 0 = base model, increments after each training
    "adapter_history": [],  # list of {version, adapter_id, timestamp, batch_size}
    "active_run_id": None,  # run ID being monitored by the background watcher
    "run_status": None,  # latest status from Prime for the active run
    "run_progress": None,  # {latest_step, max_steps, last_updated_at} from Prime progress API
    "deploying_adapter_id": None,  # adapter ID being deployed (for lazy-poll)
    "eval_status": None,  # None | "running" | "completed"
    "eval_jobs": {},  # {env_slug: eval_id}
    "eval_model_version": None,
    "eval_adapter_id": None,
}

_training_state: dict[str, Any] = {**_DEFAULT_TRAINING_STATE}

# Background task handle for the run watcher (local dev only)
_run_watcher_task: asyncio.Task | None = None

MIN_BATCH_SIZE = int(os.getenv("LAUGHLOOP_MIN_BATCH", "20"))


def _save_pipeline_state():
    """Persist pipeline state to R2 so it survives serverless cold starts."""
    if not USE_R2:
        return
    try:
        _s3_client.put_object(
            Bucket=R2_BUCKET_NAME,
            Key=R2_STATE_KEY,
            Body=json.dumps(_training_state, default=str).encode("utf-8"),
            ContentType="application/json",
        )
    except Exception:
        logger.exception("Failed to save pipeline state to R2")


def _load_pipeline_state():
    """Load pipeline state from R2.

    Called on every /pipeline request (not just cold start) to guarantee
    fresh state on serverless where module-init loading can silently fail.
    """
    global _training_state, ADAPTER_ID
    if not USE_R2:
        return
    try:
        resp = _s3_client.get_object(Bucket=R2_BUCKET_NAME, Key=R2_STATE_KEY)
        data = json.loads(resp["Body"].read().decode("utf-8"))
        _training_state.update(data)
        # Restore the adapter ID from saved state
        history = _training_state.get("adapter_history", [])
        if history:
            ADAPTER_ID = history[-1].get("adapter_id", "")
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            return  # first run, no state yet
        logger.exception("Failed to load pipeline state from R2")
    except Exception:
        logger.exception("Failed to load pipeline state from R2")


# Load persisted state on module init (serverless cold start)
_load_pipeline_state()

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
# JSONL Log Storage — R2 object store or local files
# ---------------------------------------------------------------------------

# Thread lock for safe appends from concurrent requests
_log_lock = threading.Lock()


def _r2_read_log() -> str:
    """Read the full JSONL log from R2. Returns empty string if not found."""
    try:
        resp = _s3_client.get_object(Bucket=R2_BUCKET_NAME, Key=R2_LOG_KEY)
        return resp["Body"].read().decode("utf-8")
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            return ""
        raise


def _r2_write_log(content: str):
    """Write the full JSONL log to R2."""
    _s3_client.put_object(
        Bucket=R2_BUCKET_NAME,
        Key=R2_LOG_KEY,
        Body=content.encode("utf-8"),
        ContentType="application/x-ndjson",
    )


def _append_log(record: dict):
    """Append a single JSON record to the interactions log."""
    line = json.dumps(record, default=str) + "\n"
    with _log_lock:
        if USE_R2:
            existing = _r2_read_log()
            _r2_write_log(existing + line)
        else:
            with open(INTERACTIONS_LOG, "a") as f:
                f.write(line)


def _read_all_interactions() -> list[dict]:
    """Read all interaction records from the log file."""
    if USE_R2:
        content = _r2_read_log()
    else:
        if not INTERACTIONS_LOG.exists():
            return []
        with open(INTERACTIONS_LOG) as f:
            content = f.read()

    records = []
    for line in content.splitlines():
        line = line.strip()
        if line:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def _rewrite_log(records: list[dict]):
    """Rewrite the entire log file (used for updates like feedback)."""
    content = "".join(json.dumps(r, default=str) + "\n" for r in records)
    with _log_lock:
        if USE_R2:
            _r2_write_log(content)
        else:
            with open(INTERACTIONS_LOG, "w") as f:
                f.write(content)


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
    if not USE_R2:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
    yield
    # Cancel any running watchers on shutdown (local dev only)
    global _run_watcher_task, _eval_watcher_task
    if _run_watcher_task and not _run_watcher_task.done():
        _run_watcher_task.cancel()
    if _eval_watcher_task and not _eval_watcher_task.done():
        _eval_watcher_task.cancel()


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

    # Auto-trigger pipeline when enough labeled data has been collected.
    # Reload state from R2 first so we see the real status (not stale in-memory).
    _load_pipeline_state()
    unexported_labeled = [
        r for r in records
        if r.get("feedback") is not None and r.get("exported", 0) == 0
    ]
    if (
        len(unexported_labeled) >= MIN_BATCH_SIZE
        and _training_state["status"] == "idle"
        and API_KEY  # need an API key to train
    ):
        logger.info(
            "Auto-trigger: %d unexported labeled >= %d threshold",
            len(unexported_labeled), MIN_BATCH_SIZE,
        )
        # Mark as non-idle immediately to prevent duplicate triggers
        _training_state["status"] = "exporting"
        _save_pipeline_state()
        # Await inline so it completes within the Vercel request lifecycle.
        # On local dev with background watcher, this still works fine.
        await _auto_pipeline_loop()

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


@app.get("/interactions")
async def interactions(
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0, ge=0),
):
    """Get interaction log entries for the log viewer panel."""
    records = _read_all_interactions()
    # Return newest first for the log viewer
    records.reverse()
    total = len(records)
    page = records[offset : offset + limit]
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "interactions": page,
    }


def _get_batch_files() -> list[dict]:
    """List exported training batches from R2 or local filesystem."""
    if USE_R2:
        try:
            resp = _s3_client.list_objects_v2(
                Bucket=R2_BUCKET_NAME, Prefix="batches/batch_",
            )
            batches = []
            for obj in resp.get("Contents", []):
                key = obj["Key"]
                filename = key.split("/")[-1]
                batches.append({
                    "filename": filename,
                    "records": 0,  # can't cheaply count lines in R2
                    "created_at": obj["LastModified"].isoformat(),
                    "size_bytes": obj["Size"],
                })
            batches.sort(key=lambda b: b["created_at"], reverse=True)
            return batches
        except Exception:
            logger.exception("Failed to list batches from R2")
            return []

    if not BATCH_DIR.exists():
        return []
    batches = []
    for path in sorted(BATCH_DIR.glob("batch_*.jsonl"), reverse=True):
        if path.name == "latest.jsonl":
            continue
        try:
            with open(path) as fh:
                line_count = sum(1 for _ in fh)
            stat = path.stat()
            batches.append({
                "filename": path.name,
                "records": line_count,
                "created_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                "size_bytes": stat.st_size,
            })
        except OSError:
            continue
    return batches


@app.get("/pipeline")
async def pipeline_status():
    """Get training pipeline status for the pipeline visualization panel.

    On serverless (Vercel), also lazy-polls the active training run so the
    frontend sees up-to-date status without background tasks.
    """
    # Reload state from R2 on every request — module-init loading is unreliable
    # on Vercel serverless where cold-start module execution can silently fail.
    _load_pipeline_state()

    # Lazy-poll: if there's an active run or deployment, check status via Prime API
    if _training_state["active_run_id"] and _training_state["status"] == "training":
        await _lazy_poll_run(_training_state["active_run_id"])
    elif _training_state["status"] == "deploying" and _training_state.get("deploying_adapter_id"):
        await _lazy_poll_deploy(_training_state["deploying_adapter_id"])
    elif _training_state["status"] == "deploying" and not _training_state.get("deploying_adapter_id"):
        # Recovery: serverless killed the function before _start_adapter_deploy
        # could save the adapter ID.  Retry adapter discovery from the run ID.
        run_id = _training_state.get("active_run_id")
        if run_id:
            await _start_adapter_deploy(run_id)
        else:
            # No run ID either — reset to idle to unblock the pipeline
            _training_state["status"] = "idle"
            _save_pipeline_state()
    elif _training_state["status"] == "exporting":
        # Recovery: export is fast and should never persist across cold starts.
        # If we see it on a fresh request, the previous function was killed mid-export.
        logger.warning("Recovery: resetting stuck 'exporting' state to idle")
        _training_state["status"] = "idle"
        _save_pipeline_state()
    elif _training_state["status"] == "training" and not _training_state.get("active_run_id"):
        # Recovery: training was started but the run ID was never saved.
        logger.warning("Recovery: resetting stuck 'training' state (no run ID) to idle")
        _training_state["status"] = "idle"
        _save_pipeline_state()

    records = _read_all_interactions()

    total = len(records)
    with_feedback = [r for r in records if r.get("feedback") is not None]
    unexported = [
        r for r in records
        if r.get("exported", 0) == 0 and r.get("feedback") is not None
    ]
    exported = [
        r for r in records
        if r.get("exported", 0) == 1
    ]

    batches = _get_batch_files()

    # Determine active model version display
    model_version = _training_state["model_version"]
    model_display = f"v{model_version}" if model_version > 0 else "base"

    return {
        "data_collection": {
            "total_interactions": total,
            "labeled": len(with_feedback),
            "unlabeled": total - len(with_feedback),
            "unexported": len(unexported),
            "exported": len(exported),
        },
        "batch_queue": {
            "pending_for_export": len(unexported),
            "min_batch_size": MIN_BATCH_SIZE,
            "ready_for_export": len(unexported) >= MIN_BATCH_SIZE,
            "batches": batches[:5],  # last 5 batches
        },
        "training": {
            "status": _training_state["status"],
            "current_batch": _training_state["current_batch"],
            "batches_completed": _training_state["batches_completed"],
            "last_training_time": _training_state["last_training_time"],
            "active_run_id": _training_state["active_run_id"],
            "run_status": _training_state["run_status"],
            "run_progress": _training_state.get("run_progress"),
        },
        "model": {
            "name": MODEL_NAME,
            "version": model_version,
            "version_display": model_display,
            "adapter_id": ADAPTER_ID or None,
            "adapter_history": _training_state["adapter_history"][-5:],
        },
    }


# ---------------------------------------------------------------------------
# Pipeline Action Endpoints
# ---------------------------------------------------------------------------


def _prime_headers() -> dict[str, str]:
    """Build common headers for Prime API calls."""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    if TEAM_ID:
        headers["X-Prime-Team-ID"] = TEAM_ID
    return headers




# ---------------------------------------------------------------------------
# In-process export — works on Vercel (no subprocess)
# ---------------------------------------------------------------------------

_EXPORT_SYSTEM_PROMPT = SYSTEM_PROMPT  # reuse the same prompt for training data


def _build_training_record(interaction: dict, context: list[dict]) -> dict:
    """Convert an interaction into a training-ready record."""
    messages: list[dict[str, str]] = [{"role": "system", "content": _EXPORT_SYSTEM_PROMPT}]
    for ctx in context[-4:]:
        messages.append({"role": "user", "content": ctx["user_message"]})
        messages.append({"role": "assistant", "content": ctx["assistant_message"]})
    messages.append({"role": "user", "content": interaction["user_message"]})

    reward = 1.0 if interaction.get("feedback") == 1 else 0.0
    return {
        "question": interaction["user_message"],
        "answer": interaction["assistant_message"],
        "prompt": messages,
        "info": {
            "interaction_id": interaction["id"],
            "session_id": interaction["session_id"],
            "timestamp": interaction["timestamp"],
            "model": interaction.get("model", MODEL_NAME),
            "adapter_id": interaction.get("adapter_id", ""),
            "human_reward": reward,
            "feedback": "funny" if interaction.get("feedback") == 1 else "not_funny",
        },
    }


def _inline_export(records: list[dict]) -> tuple[int, str | None]:
    """Export unexported labeled records in-process.

    Returns (records_exported, batch_key_or_path).
    Marks exported records in the passed-in list (caller must persist).
    """
    unexported = [
        r for r in records
        if r.get("feedback") is not None and r.get("exported", 0) == 0
    ]
    if len(unexported) < 1:
        return 0, None

    # Group by session for context
    sessions: dict[str, list[dict]] = {}
    for ix in unexported:
        sid = ix["session_id"]
        sessions.setdefault(sid, []).append(ix)

    training_records: list[dict] = []
    for _sid, session_ixs in sessions.items():
        for i, ix in enumerate(session_ixs):
            training_records.append(_build_training_record(ix, session_ixs[:i]))

    unique_count = len(training_records)

    # Duplicate samples to increase effective training set size for small batches.
    sample_multiplier = int(os.environ.get("LAUGHLOOP_SAMPLE_MULTIPLIER", "5"))
    if sample_multiplier > 1:
        training_records = training_records * sample_multiplier

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    batch_content = "\n".join(json.dumps(r) for r in training_records) + "\n"

    if USE_R2:
        batch_key = f"batches/batch_{timestamp}.jsonl"
        _s3_client.put_object(
            Bucket=R2_BUCKET_NAME,
            Key=batch_key,
            Body=batch_content.encode("utf-8"),
            ContentType="application/x-ndjson",
        )
        dest = batch_key
    else:
        BATCH_DIR.mkdir(parents=True, exist_ok=True)
        batch_path = BATCH_DIR / f"batch_{timestamp}.jsonl"
        batch_path.write_text(batch_content)
        # Create latest.jsonl symlink for the local CLI training workflow
        latest_path = BATCH_DIR / "latest.jsonl"
        if latest_path.exists() or latest_path.is_symlink():
            latest_path.unlink()
        try:
            latest_path.symlink_to(batch_path.name)
        except OSError:
            import shutil
            shutil.copy2(batch_path, latest_path)
        dest = str(batch_path)

    # Mark as exported
    exported_ids = {ix["id"] for ix in unexported}
    for r in records:
        if r.get("id") in exported_ids:
            r["exported"] = 1

    return unique_count, dest


@app.post("/pipeline/export")
async def pipeline_export():
    """Trigger batch export from the interaction log (in-process, no subprocess)."""
    _training_state["status"] = "exporting"
    try:
        records = _read_all_interactions()
        count, dest = _inline_export(records)
        if count > 0:
            _rewrite_log(records)  # persist exported marks
        _training_state["status"] = "idle"
        _save_pipeline_state()
        return {
            "success": True,
            "records_exported": count,
            "batch_file": dest,
        }
    except Exception as e:
        _training_state["status"] = "idle"
        _save_pipeline_state()
        raise HTTPException(status_code=500, detail=str(e))


async def _start_training_run_api() -> str | None:
    """Start an RL training run via Prime REST API. Returns the run ID."""
    payload = {
        "model": {"name": MODEL_NAME},
        "environments": [{"id": "prime/laughloop-reward"}],
        "max_steps": 50,
        "batch_size": 64,
        "rollouts_per_example": 4,
        "learning_rate": 5e-6,
        "max_tokens": 512,
        "temperature": 0.9,
        "checkpoint_interval": 25,
        "checkpoint_keep_cloud": 3,
        "adapter_interval": 0,
        "adapter_keep_last": 3,
    }
    async with httpx.AsyncClient(timeout=30) as http_client:
        resp = await http_client.post(
            f"{PRIME_BASE_URL}/api/v1/rft/runs",
            headers=_prime_headers(),
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
    return data.get("run", {}).get("id")


@app.post("/pipeline/train")
async def pipeline_train():
    """Start an RL training run on Prime via REST API."""
    _training_state["status"] = "training"
    try:
        run_id = await _start_training_run_api()

        if not run_id:
            _training_state["status"] = "idle"
            _save_pipeline_state()
            return {"success": False, "error": "No run ID returned from API"}

        _training_state["current_batch"] = run_id
        _training_state["last_training_time"] = datetime.now(timezone.utc).isoformat()
        _training_state["batches_completed"] += 1
        _training_state["active_run_id"] = run_id
        _training_state["run_status"] = "QUEUED"
        _training_state["status"] = "training"
        # On long-lived servers (local dev), start background watcher
        _start_run_watcher(run_id)

        _save_pipeline_state()
        return {
            "success": True,
            "run_id": run_id,
        }
    except Exception as e:
        _training_state["status"] = "idle"
        _save_pipeline_state()
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Background Run Watcher — polls Prime, auto-deploys adapter on completion
# ---------------------------------------------------------------------------


def _start_run_watcher(run_id: str):
    """Kick off a background asyncio task that monitors a training run."""
    global _run_watcher_task
    # Cancel any previous watcher
    if _run_watcher_task and not _run_watcher_task.done():
        _run_watcher_task.cancel()
    _run_watcher_task = asyncio.create_task(_watch_run(run_id))


async def _watch_run(run_id: str):
    """Poll Prime API for run status; when COMPLETED, deploy the adapter.

    Used for long-lived servers (local dev). On serverless, _lazy_poll_run
    handles this instead.
    """
    global ADAPTER_ID
    poll_interval = 30  # seconds between status checks
    max_polls = 360  # ~3 hours max before giving up
    logger.info("Run watcher started for %s", run_id)

    try:
        for _poll_count in range(max_polls):
            await asyncio.sleep(poll_interval)
            try:
                async with httpx.AsyncClient(timeout=30) as http_client:
                    resp = await http_client.get(
                        f"{PRIME_BASE_URL}/api/v1/rft/runs/{run_id}",
                        headers=_prime_headers(),
                    )
                    resp.raise_for_status()
                    run_data = resp.json()

                status = run_data.get("status", "UNKNOWN")
                _training_state["run_status"] = status
                _save_pipeline_state()
                logger.info("Run %s status: %s", run_id, status)

                if status == "COMPLETED":
                    logger.info("Run %s completed — deploying adapter", run_id)
                    _training_state["status"] = "deploying"
                    await _auto_deploy_adapter(run_id)
                    return

                if status in ("FAILED", "STOPPED", "CANCELLED"):
                    logger.warning("Run %s ended with status %s", run_id, status)
                    _training_state["status"] = "idle"
                    _training_state["active_run_id"] = None
                    _training_state["run_status"] = None
                    _save_pipeline_state()
                    return

                # Still running — keep polling

            except Exception:
                logger.exception("Error polling run %s", run_id)
                # Keep trying — transient network errors shouldn't kill the watcher

        # Exhausted max polls
        logger.warning("Run watcher for %s timed out after %d polls", run_id, max_polls)
        _training_state["status"] = "idle"
        _training_state["active_run_id"] = None
        _training_state["run_status"] = None
        _save_pipeline_state()

    except asyncio.CancelledError:
        logger.info("Run watcher for %s cancelled", run_id)
        return


async def _lazy_poll_run(run_id: str):
    """Single-shot poll of a training run — used on serverless where we
    can't keep a background watcher alive.  Called from GET /pipeline.

    Also fetches training progress (steps completed) from the Prime
    progress API so the frontend can show a progress bar.
    """
    global ADAPTER_ID
    try:
        async with httpx.AsyncClient(timeout=15) as http_client:
            # Fetch run status
            resp = await http_client.get(
                f"{PRIME_BASE_URL}/api/v1/rft/runs/{run_id}",
                headers=_prime_headers(),
            )
            resp.raise_for_status()
            run_data = resp.json()

            # Fetch training progress (best-effort, don't fail if unavailable)
            try:
                progress_resp = await http_client.get(
                    f"{PRIME_BASE_URL}/api/v1/rft/runs/{run_id}/progress",
                    headers=_prime_headers(),
                )
                if progress_resp.status_code == 200:
                    progress_data = progress_resp.json()
                    max_steps = run_data.get("max_steps", 50)
                    _training_state["run_progress"] = {
                        "latest_step": progress_data.get("latest_step", 0),
                        "max_steps": max_steps,
                        "last_updated_at": progress_data.get("last_updated_at"),
                    }
            except Exception:
                pass  # Progress is nice-to-have, not critical

        status = run_data.get("status", "UNKNOWN")
        _training_state["run_status"] = status

        if status == "COMPLETED":
            _training_state["run_progress"] = None
            _training_state["status"] = "deploying"
            _save_pipeline_state()
            # Kick off adapter discovery + deploy request (non-blocking).
            # The actual deployment polling is handled by _lazy_poll_deploy
            # on subsequent GET /pipeline requests.
            await _start_adapter_deploy(run_id)

        elif status in ("FAILED", "STOPPED", "CANCELLED"):
            _training_state["status"] = "idle"
            _training_state["active_run_id"] = None
            _training_state["run_status"] = None
            _training_state["run_progress"] = None
            _save_pipeline_state()

        else:
            _save_pipeline_state()

    except Exception:
        logger.exception("Lazy poll failed for run %s", run_id)


async def _start_adapter_deploy(run_id: str):
    """Find the best adapter for a completed run and issue the deploy request.

    Stores `deploying_adapter_id` in state so _lazy_poll_deploy can track it
    on subsequent GET /pipeline requests.  Does NOT poll — returns quickly.
    """
    try:
        async with httpx.AsyncClient(timeout=30) as http_client:
            resp = await http_client.get(
                f"{PRIME_BASE_URL}/api/v1/deployments/adapters",
                headers=_prime_headers(),
                params={"page": 1, "limit": 50},
            )
            resp.raise_for_status()
            data = resp.json()

        adapters = data.get("data", data.get("adapters", []))
        matching = [
            a for a in adapters
            if a.get("rftRunId") == run_id and a.get("status") == "READY"
        ]

        if not matching:
            logger.warning("No READY adapters found for run %s", run_id)
            _training_state["status"] = "idle"
            _training_state["active_run_id"] = None
            _training_state["run_status"] = None
            _training_state["deploying_adapter_id"] = None
            _save_pipeline_state()
            return

        matching.sort(key=lambda a: a.get("step") or 0, reverse=True)
        adapter = matching[0]
        adapter_id = adapter["id"]
        logger.info("Found adapter %s for run %s — issuing deploy request", adapter_id, run_id)

        # Issue deploy request
        async with httpx.AsyncClient(timeout=30) as http_client:
            resp = await http_client.post(
                f"{PRIME_BASE_URL}/api/v1/deployments/adapters/{adapter_id}/deploy",
                headers=_prime_headers(),
            )
            resp.raise_for_status()

        # Save adapter ID so lazy-poll can track deployment progress
        _training_state["deploying_adapter_id"] = adapter_id
        _save_pipeline_state()
        logger.info("Deploy request sent for adapter %s — lazy-poll will track it", adapter_id)

    except Exception:
        logger.exception("Error starting adapter deploy for run %s", run_id)
        _training_state["status"] = "idle"
        _training_state["active_run_id"] = None
        _training_state["run_status"] = None
        _training_state["deploying_adapter_id"] = None
        _save_pipeline_state()


async def _lazy_poll_deploy(adapter_id: str):
    """Single-shot poll of adapter deployment status — called from GET /pipeline
    when status is 'deploying'.  Returns quickly.
    """
    global ADAPTER_ID
    try:
        async with httpx.AsyncClient(timeout=15) as http_client:
            resp = await http_client.get(
                f"{PRIME_BASE_URL}/api/v1/deployments/adapters/{adapter_id}",
                headers=_prime_headers(),
            )
            resp.raise_for_status()
            adapter_data = resp.json()

        deploy_status = adapter_data.get("deploymentStatus", "")
        logger.info("Lazy-poll deploy: adapter %s status=%s", adapter_id, deploy_status)

        if deploy_status == "DEPLOYED":
            # Guard: another code path (background watcher) may have already handled this
            if _training_state["status"] != "deploying":
                return
            ADAPTER_ID = adapter_id
            _training_state["model_version"] += 1
            _training_state["adapter_history"].append({
                "version": _training_state["model_version"],
                "adapter_id": adapter_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "batch_size": adapter_data.get("step", 0),
            })
            _training_state["status"] = "idle"
            _training_state["active_run_id"] = None
            _training_state["run_status"] = None
            _training_state["deploying_adapter_id"] = None
            _save_pipeline_state()
            logger.info(
                "Adapter %s deployed and hot-swapped — now model v%d",
                adapter_id, _training_state["model_version"],
            )
            # Auto-trigger evals for the newly deployed model (serverless)
            await _submit_evals_serverless(
                MODEL_NAME, _training_state["model_version"], adapter_id,
            )

        elif deploy_status in ("DEPLOY_FAILED", "UNLOADING", "UNLOAD_FAILED"):
            logger.error("Adapter %s deployment failed: %s", adapter_id, deploy_status)
            _training_state["status"] = "idle"
            _training_state["active_run_id"] = None
            _training_state["run_status"] = None
            _training_state["deploying_adapter_id"] = None
            _save_pipeline_state()

        # else: still deploying — state unchanged, next poll will check again

    except Exception:
        logger.exception("Lazy-poll deploy failed for adapter %s", adapter_id)


async def _auto_deploy_adapter(run_id: str) -> bool:
    """Find the latest adapter for a completed run and deploy it.

    Used by the background watcher on long-lived servers and by the
    POST /pipeline/deploy endpoint.  On serverless, prefer
    _start_adapter_deploy + _lazy_poll_deploy instead.

    Returns True if an adapter was successfully deployed, False otherwise.
    """
    global ADAPTER_ID
    try:
        async with httpx.AsyncClient(timeout=30) as http_client:
            resp = await http_client.get(
                f"{PRIME_BASE_URL}/api/v1/deployments/adapters",
                headers=_prime_headers(),
                params={"page": 1, "limit": 50},
            )
            resp.raise_for_status()
            data = resp.json()

        adapters = data.get("data", data.get("adapters", []))
        matching = [
            a for a in adapters
            if a.get("rftRunId") == run_id and a.get("status") == "READY"
        ]

        if not matching:
            logger.warning("No READY adapters found for run %s", run_id)
            _training_state["status"] = "idle"
            _training_state["active_run_id"] = None
            _training_state["run_status"] = None
            _training_state["deploying_adapter_id"] = None
            _save_pipeline_state()
            return False

        matching.sort(key=lambda a: a.get("step") or 0, reverse=True)
        adapter = matching[0]
        adapter_id = adapter["id"]
        logger.info("Found adapter %s for run %s", adapter_id, run_id)

        # Deploy it
        async with httpx.AsyncClient(timeout=30) as http_client:
            resp = await http_client.post(
                f"{PRIME_BASE_URL}/api/v1/deployments/adapters/{adapter_id}/deploy",
                headers=_prime_headers(),
            )
            resp.raise_for_status()

        _training_state["deploying_adapter_id"] = adapter_id
        _save_pipeline_state()

        # Poll deployment status (up to 5 minutes) — only on long-lived servers
        for _ in range(30):
            await asyncio.sleep(10)
            async with httpx.AsyncClient(timeout=30) as http_client:
                resp = await http_client.get(
                    f"{PRIME_BASE_URL}/api/v1/deployments/adapters/{adapter_id}",
                    headers=_prime_headers(),
                )
                resp.raise_for_status()
                adapter_data = resp.json()

            deploy_status = adapter_data.get("deploymentStatus", "")
            logger.info("Adapter %s deployment status: %s", adapter_id, deploy_status)

            if deploy_status == "DEPLOYED":
                # Guard: lazy-poll may have already handled this transition
                if _training_state["status"] != "deploying":
                    return True
                ADAPTER_ID = adapter_id
                _training_state["model_version"] += 1
                _training_state["adapter_history"].append({
                    "version": _training_state["model_version"],
                    "adapter_id": adapter_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "batch_size": adapter.get("step", 0),
                })
                _training_state["status"] = "idle"
                _training_state["active_run_id"] = None
                _training_state["run_status"] = None
                _training_state["deploying_adapter_id"] = None
                _save_pipeline_state()
                logger.info(
                    "Adapter %s deployed and hot-swapped — now model v%d",
                    adapter_id, _training_state["model_version"],
                )
                # Auto-trigger evals for the newly deployed model (background)
                _start_eval_watcher(
                    MODEL_NAME, _training_state["model_version"], adapter_id,
                )
                return True

            if deploy_status in ("DEPLOY_FAILED", "UNLOADING", "UNLOAD_FAILED"):
                logger.error("Adapter %s deployment failed: %s", adapter_id, deploy_status)
                break

        _training_state["status"] = "idle"
        _training_state["active_run_id"] = None
        _training_state["run_status"] = None
        _training_state["deploying_adapter_id"] = None
        _save_pipeline_state()
        return False

    except Exception:
        logger.exception("Error auto-deploying adapter for run %s", run_id)
        _training_state["status"] = "idle"
        _training_state["active_run_id"] = None
        _training_state["run_status"] = None
        _training_state["deploying_adapter_id"] = None
        _save_pipeline_state()
        return False


# ---------------------------------------------------------------------------
# Auto-Pipeline Loop — export + train + deploy triggered from feedback
# ---------------------------------------------------------------------------


async def _auto_pipeline_loop():
    """Full pipeline: export labeled data → start training run → track it.

    Awaited inline from the feedback endpoint so it completes within the
    Vercel request lifecycle (fire-and-forget tasks are killed on serverless).
    Caller must set status to "exporting" and save state before calling.
    """
    try:
        # 1. Export (status already set to "exporting" by caller)
        logger.info("Auto-pipeline: exporting batch")

        records = _read_all_interactions()
        count, dest = _inline_export(records)
        if count > 0:
            _rewrite_log(records)
        logger.info("Auto-pipeline: exported %d records to %s", count, dest)

        if count == 0:
            _training_state["status"] = "idle"
            _save_pipeline_state()
            return

        # 2. Start training
        _training_state["status"] = "training"
        _save_pipeline_state()
        logger.info("Auto-pipeline: starting training run")

        run_id = await _start_training_run_api()
        if not run_id:
            logger.error("Auto-pipeline: failed to get run ID")
            _training_state["status"] = "idle"
            _save_pipeline_state()
            return

        _training_state["current_batch"] = run_id
        _training_state["last_training_time"] = datetime.now(timezone.utc).isoformat()
        _training_state["batches_completed"] += 1
        _training_state["active_run_id"] = run_id
        _training_state["run_status"] = "QUEUED"
        _save_pipeline_state()
        logger.info("Auto-pipeline: training run %s started", run_id)

        # On long-lived servers, start the background watcher.
        # On serverless, lazy-polling in GET /pipeline handles the rest.
        _start_run_watcher(run_id)

    except Exception:
        logger.exception("Auto-pipeline loop failed")
        _training_state["status"] = "idle"
        _save_pipeline_state()


@app.get("/pipeline/runs")
async def pipeline_runs():
    """List recent RL training runs from Prime."""
    try:
        async with httpx.AsyncClient(timeout=30) as http_client:
            resp = await http_client.get(
                f"{PRIME_BASE_URL}/api/v1/rft/runs",
                headers=_prime_headers(),
                params={"page": 1, "limit": 10},
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "success": True,
                "runs": data.get("data", data.get("runs", [])),
            }
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/pipeline/deploy")
async def pipeline_deploy(run_id: str | None = None):
    """Deploy the latest adapter from a completed training run via API."""
    global ADAPTER_ID
    _training_state["status"] = "deploying"
    try:
        target_run = run_id or _training_state.get("active_run_id")
        if not target_run:
            _training_state["status"] = "idle"
            _save_pipeline_state()
            return {"success": False, "error": "No run ID specified and no active run"}

        deployed = await _auto_deploy_adapter(target_run)
        if not deployed:
            return {
                "success": False,
                "error": f"Adapter deployment failed for run {target_run}",
                "adapter_id": ADAPTER_ID or None,
                "model_version": _training_state["model_version"],
            }
        return {
            "success": True,
            "adapter_id": ADAPTER_ID or None,
            "model_version": _training_state["model_version"],
        }
    except Exception as e:
        _training_state["status"] = "idle"
        _save_pipeline_state()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "model": MODEL_NAME,
        "adapter": ADAPTER_ID or None,
        "storage": "r2" if USE_R2 else "local",
    }


# ---------------------------------------------------------------------------
# Eval Results — stored in R2 or local file
# ---------------------------------------------------------------------------

R2_EVALS_KEY = "evals/results.json"
EVALS_FILE = LOG_DIR / "evals.json"

# The 4 eval environments we track
EVAL_ENVIRONMENTS = [
    "primeintellect/aime2026",
    "primeintellect/gsm8k",
    "primeintellect/wordle",
    "prime/tau2-synth",
]

# Hosted eval settings
EVAL_NUM_EXAMPLES = int(os.getenv("LAUGHLOOP_EVAL_NUM_EXAMPLES", "10"))
EVAL_ROLLOUTS_PER_EXAMPLE = int(os.getenv("LAUGHLOOP_EVAL_ROLLOUTS", "3"))
EVAL_POLL_INTERVAL = int(os.getenv("LAUGHLOOP_EVAL_POLL_INTERVAL", "15"))
EVAL_MAX_POLLS = int(os.getenv("LAUGHLOOP_EVAL_MAX_POLLS", "120"))  # ~30 min

# Background eval watcher task (local dev only)
_eval_watcher_task: asyncio.Task | None = None


def _read_eval_results() -> dict:
    """Read eval results from R2 or local file."""
    if USE_R2:
        try:
            resp = _s3_client.get_object(Bucket=R2_BUCKET_NAME, Key=R2_EVALS_KEY)
            return json.loads(resp["Body"].read().decode("utf-8"))
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                return {"environments": EVAL_ENVIRONMENTS, "baseline": {}, "runs": []}
            logger.exception("Failed to read eval results from R2")
            raise
        except Exception:
            logger.exception("Failed to read eval results from R2")
            raise
    # Local file fallback
    if EVALS_FILE.exists():
        return json.loads(EVALS_FILE.read_text())
    return {"environments": EVAL_ENVIRONMENTS, "baseline": {}, "runs": []}


def _write_eval_results(data: dict):
    """Write eval results to R2 or local file."""
    payload = json.dumps(data, indent=2)
    if USE_R2:
        try:
            _s3_client.put_object(
                Bucket=R2_BUCKET_NAME,
                Key=R2_EVALS_KEY,
                Body=payload.encode("utf-8"),
                ContentType="application/json",
            )
        except Exception:
            logger.exception("Failed to write eval results to R2")
            raise
        return
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    EVALS_FILE.write_text(payload)


# ---------------------------------------------------------------------------
# Hosted Eval Runner — triggers evals on Prime platform, polls for results
# ---------------------------------------------------------------------------


async def _resolve_environment_id(owner: str, name: str) -> str | None:
    """Resolve an environment slug (owner/name) to its platform ID."""
    try:
        async with httpx.AsyncClient(timeout=15) as http_client:
            resp = await http_client.get(
                f"{PRIME_BASE_URL}/api/v1/environmentshub/{owner}/{name}/@latest",
                headers=_prime_headers(),
            )
            resp.raise_for_status()
            data = resp.json()
            details = data.get("data", data)
            return details.get("id")
    except Exception:
        logger.exception("Failed to resolve environment %s/%s", owner, name)
        return None


async def _submit_hosted_eval(
    environment_id: str,
    model_name: str,
    num_examples: int = EVAL_NUM_EXAMPLES,
    rollouts_per_example: int = EVAL_ROLLOUTS_PER_EXAMPLE,
    eval_name: str | None = None,
) -> str | None:
    """Submit a hosted evaluation to the Prime platform. Returns the evaluation ID."""
    payload: dict[str, Any] = {
        "environment_ids": [environment_id],
        "inference_model": model_name,
        "eval_config": {
            "num_examples": num_examples,
            "rollouts_per_example": rollouts_per_example,
            "allow_sandbox_access": False,
            "allow_instances_access": False,
        },
    }
    if eval_name:
        payload["name"] = eval_name
    if TEAM_ID:
        payload["team_id"] = TEAM_ID

    try:
        async with httpx.AsyncClient(timeout=30) as http_client:
            resp = await http_client.post(
                f"{PRIME_BASE_URL}/api/v1/hosted-evaluations",
                headers=_prime_headers(),
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            eval_id = data.get("evaluation_id")
            eval_ids = data.get("evaluation_ids")
            if eval_id:
                return eval_id
            if eval_ids:
                return eval_ids[0]
            logger.error("No evaluation ID in response: %s", data)
            return None
    except Exception:
        logger.exception("Failed to submit hosted eval")
        return None


async def _poll_eval_status(eval_id: str) -> dict[str, Any] | None:
    """Poll a single evaluation's status. Returns the eval data dict."""
    try:
        async with httpx.AsyncClient(timeout=15) as http_client:
            resp = await http_client.get(
                f"{PRIME_BASE_URL}/api/v1/evaluations/{eval_id}",
                headers=_prime_headers(),
            )
            resp.raise_for_status()
            return resp.json()
    except Exception:
        logger.exception("Failed to poll eval %s", eval_id)
        return None


async def _extract_eval_score(eval_id: str) -> float | None:
    """Extract the aggregate score from a completed evaluation.

    Checks metrics first, then falls back to averaging sample scores.
    """
    eval_data = await _poll_eval_status(eval_id)
    if not eval_data:
        return None

    # Check metrics for avg_score or similar
    metrics = eval_data.get("metrics") or {}
    for key in ("avg_score", "mean_score", "score", "accuracy", "reward"):
        if key in metrics and metrics[key] is not None:
            return float(metrics[key])

    # Fallback: fetch samples and average their scores
    try:
        async with httpx.AsyncClient(timeout=30) as http_client:
            resp = await http_client.get(
                f"{PRIME_BASE_URL}/api/v1/evaluations/{eval_id}/samples",
                headers=_prime_headers(),
                params={"page": 1, "limit": 500},
            )
            resp.raise_for_status()
            samples_data = resp.json()
            samples = samples_data.get("samples", [])
            scores = [
                s["score"] for s in samples
                if s.get("score") is not None
            ]
            if scores:
                return sum(scores) / len(scores)
    except Exception:
        logger.exception("Failed to fetch samples for eval %s", eval_id)

    return None


async def _run_evals_for_model(
    model_name: str,
    model_version: int,
    adapter_id: str | None = None,
) -> dict[str, float]:
    """Run hosted evals for all 4 environments and return scores.

    Submits all evals in parallel, then polls until all complete.
    Returns a dict of {env_name: score}.
    """
    logger.info(
        "Starting evals for %s (version=%d, adapter=%s)",
        model_name, model_version, adapter_id or "base",
    )

    # Resolve environment IDs
    env_ids: dict[str, str] = {}
    for env_slug in EVAL_ENVIRONMENTS:
        owner, name = env_slug.split("/", 1)
        env_id = await _resolve_environment_id(owner, name)
        if env_id:
            env_ids[env_slug] = env_id
        else:
            logger.warning("Could not resolve environment: %s", env_slug)

    if not env_ids:
        logger.error("No environments resolved — skipping evals")
        return {}

    # Submit hosted evals for each environment
    eval_jobs: dict[str, str] = {}  # env_slug -> evaluation_id
    for env_slug, env_id in env_ids.items():
        label = "base" if model_version == 0 else f"v{model_version}"
        eval_name = f"laughloop-{label}-{env_slug.replace('/', '-')}"
        eval_id = await _submit_hosted_eval(
            environment_id=env_id,
            model_name=model_name,
            eval_name=eval_name,
        )
        if eval_id:
            eval_jobs[env_slug] = eval_id
            logger.info("Submitted eval for %s: %s", env_slug, eval_id)
        else:
            logger.warning("Failed to submit eval for %s", env_slug)

    if not eval_jobs:
        logger.error("No evals submitted — skipping")
        return {}

    # Poll until all evals complete (or timeout)
    terminal_statuses = {"COMPLETED", "FAILED", "TIMEOUT", "CANCELLED"}
    completed: dict[str, str] = {}  # env_slug -> status

    for _ in range(EVAL_MAX_POLLS):
        await asyncio.sleep(EVAL_POLL_INTERVAL)

        for env_slug, eval_id in eval_jobs.items():
            if env_slug in completed:
                continue
            eval_data = await _poll_eval_status(eval_id)
            if not eval_data:
                continue
            status = eval_data.get("status", "UNKNOWN")
            if status in terminal_statuses:
                completed[env_slug] = status
                logger.info("Eval %s (%s) finished: %s", env_slug, eval_id, status)

        if len(completed) == len(eval_jobs):
            break

    # Extract scores from completed evals
    scores: dict[str, float] = {}
    for env_slug, eval_id in eval_jobs.items():
        status = completed.get(env_slug)
        if status != "COMPLETED":
            logger.warning("Eval %s did not complete (status=%s)", env_slug, status)
            continue
        score = await _extract_eval_score(eval_id)
        if score is not None:
            scores[env_slug] = score
            logger.info("Eval %s score: %.4f", env_slug, score)
        else:
            logger.warning("Could not extract score for %s", env_slug)

    # Store results
    if scores:
        data = _read_eval_results()
        entry = {
            "model_version": model_version,
            "adapter_id": adapter_id,
            "scores": scores,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if model_version == 0:
            data["baseline"] = scores
        else:
            data["runs"].append(entry)
        _write_eval_results(data)
        logger.info("Stored eval results for version %d: %s", model_version, scores)

    return scores


async def _auto_eval_after_deploy(
    model_name: str,
    model_version: int,
    adapter_id: str | None = None,
):
    """Background task: run evals after adapter deployment completes."""
    try:
        await _run_evals_for_model(model_name, model_version, adapter_id)
    except Exception:
        logger.exception("Auto-eval failed for version %d", model_version)


def _start_eval_watcher(
    model_name: str,
    model_version: int,
    adapter_id: str | None = None,
):
    """Kick off a background asyncio task to run evals (local dev only)."""
    global _eval_watcher_task
    if _eval_watcher_task and not _eval_watcher_task.done():
        _eval_watcher_task.cancel()
    _eval_watcher_task = asyncio.create_task(
        _auto_eval_after_deploy(model_name, model_version, adapter_id)
    )


async def _lazy_poll_evals():
    """Single-shot poll of active eval jobs — used on serverless.
    Called from GET /evals when eval_status is 'running'.
    """
    _load_pipeline_state()
    eval_jobs = _training_state.get("eval_jobs", {})
    if not eval_jobs:
        return

    terminal_statuses = {"COMPLETED", "FAILED", "TIMEOUT", "CANCELLED"}
    all_done = True
    scores: dict[str, float] = {}

    for env_slug, eval_id in eval_jobs.items():
        eval_data = await _poll_eval_status(eval_id)
        if not eval_data:
            all_done = False
            continue
        status = eval_data.get("status", "UNKNOWN")
        if status not in terminal_statuses:
            all_done = False
            continue
        if status == "COMPLETED":
            score = await _extract_eval_score(eval_id)
            if score is not None:
                scores[env_slug] = score

    if all_done and scores:
        model_version = _training_state.get("eval_model_version", 0)
        adapter_id = _training_state.get("eval_adapter_id")
        data = _read_eval_results()
        entry = {
            "model_version": model_version,
            "adapter_id": adapter_id,
            "scores": scores,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if model_version == 0:
            data["baseline"] = scores
        else:
            data["runs"].append(entry)
        _write_eval_results(data)
        logger.info("Lazy-poll: stored eval results for version %d", model_version)
        _training_state["eval_status"] = "completed"
        _training_state["eval_jobs"] = {}
        _save_pipeline_state()
    elif all_done:
        # All done but no scores extracted
        _training_state["eval_status"] = "completed"
        _training_state["eval_jobs"] = {}
        _save_pipeline_state()


async def _submit_evals_serverless(
    model_name: str,
    model_version: int,
    adapter_id: str | None = None,
):
    """Submit hosted evals and save job IDs to state for lazy-polling.
    Used on serverless where we can't keep a background task alive.
    """
    env_ids: dict[str, str] = {}
    for env_slug in EVAL_ENVIRONMENTS:
        owner, name = env_slug.split("/", 1)
        env_id = await _resolve_environment_id(owner, name)
        if env_id:
            env_ids[env_slug] = env_id

    eval_jobs: dict[str, str] = {}
    for env_slug, env_id in env_ids.items():
        label = "base" if model_version == 0 else f"v{model_version}"
        eval_name = f"laughloop-{label}-{env_slug.replace('/', '-')}"
        eval_id = await _submit_hosted_eval(
            environment_id=env_id,
            model_name=model_name,
            eval_name=eval_name,
        )
        if eval_id:
            eval_jobs[env_slug] = eval_id

    if eval_jobs:
        _training_state["eval_status"] = "running"
        _training_state["eval_jobs"] = eval_jobs
        _training_state["eval_model_version"] = model_version
        _training_state["eval_adapter_id"] = adapter_id
        _save_pipeline_state()
        logger.info("Submitted %d evals for lazy-polling", len(eval_jobs))


# ---------------------------------------------------------------------------
# Eval Endpoints
# ---------------------------------------------------------------------------


class EvalResultSubmission(BaseModel):
    """Submit eval results for a model version."""
    model_version: int  # 0 = base model
    adapter_id: str | None = None
    scores: dict[str, float]  # env_name -> score (0.0 - 1.0)


@app.get("/evals")
async def get_evals():
    """Get all eval results for plotting.

    On serverless, also lazy-polls active eval jobs.
    """
    # Lazy-poll running evals on serverless
    _load_pipeline_state()
    if _training_state.get("eval_status") == "running":
        await _lazy_poll_evals()

    return _read_eval_results()


@app.post("/evals")
async def submit_evals(submission: EvalResultSubmission):
    """Submit eval results for a model version.

    Used after running evals locally or via CI to record scores.
    """
    data = _read_eval_results()

    entry = {
        "model_version": submission.model_version,
        "adapter_id": submission.adapter_id,
        "scores": submission.scores,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if submission.model_version == 0:
        # Base model scores — update the baseline
        data["baseline"] = submission.scores
    else:
        data["runs"].append(entry)

    _write_eval_results(data)
    return {"success": True, "entry": entry}


@app.post("/evals/run")
async def trigger_eval_run(
    model_version: int = Query(default=0, description="Model version (0 = base)"),
):
    """Manually trigger an eval run for a model version.

    Submits hosted evals to Prime platform for all 4 environments.
    On local dev, runs as a background task that polls until completion.
    On serverless, submits and returns immediately — lazy-polling handles the rest.
    """
    adapter_id = ADAPTER_ID if model_version > 0 else None
    model_name = MODEL_NAME

    # Check if evals are already running
    _load_pipeline_state()
    if _training_state.get("eval_status") == "running":
        return {
            "success": False,
            "error": "Evals are already running",
            "eval_jobs": _training_state.get("eval_jobs", {}),
        }

    # On long-lived servers, use background task
    try:
        asyncio.get_running_loop()
        has_background = not os.getenv("VERCEL")
    except RuntimeError:
        has_background = False

    if has_background:
        _training_state["eval_status"] = "running"
        _save_pipeline_state()
        _start_eval_watcher(model_name, model_version, adapter_id)
        return {
            "success": True,
            "mode": "background",
            "message": f"Eval run started for version {model_version}",
        }
    else:
        await _submit_evals_serverless(model_name, model_version, adapter_id)
        return {
            "success": True,
            "mode": "serverless",
            "message": "Evals submitted — poll GET /evals for results",
            "eval_jobs": _training_state.get("eval_jobs", {}),
        }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
