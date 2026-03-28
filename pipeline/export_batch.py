"""
LaughLoop Data Pipeline — Export interactions to training-ready JSONL.

Reads from the SQLite log database, exports interactions that have feedback
but haven't been exported yet, and writes them as training-ready JSONL.

Each record contains:
  - question: the user's message (with conversation context)
  - answer: the assistant's response
  - reward: 1.0 if user clicked Haha, 0.0 if not
  - info: metadata (session_id, timestamp, model, etc.)

Usage:
  python export_batch.py                        # Export to default location
  python export_batch.py --output ./data/batch_003.jsonl
  python export_batch.py --min-batch-size 50    # Only export if 50+ new interactions
"""

import argparse
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

# Default paths
DEFAULT_DB = Path(__file__).parent.parent / "app" / "backend" / "laughloop.db"
DEFAULT_OUTPUT_DIR = Path(__file__).parent.parent / "data" / "batches"
SYSTEM_PROMPT = """You are LaughLoop, a hilariously witty AI assistant. Your #1 goal is to make the user laugh.

Rules:
- Every response should try to be genuinely funny — use wordplay, unexpected twists, absurd comparisons, self-deprecation, observational humor, or whatever lands best.
- Stay helpful — if someone asks a real question, answer it AND make it funny.
- Keep responses concise. The best jokes don't need paragraphs.
- Vary your humor style. Don't repeat the same schtick.
- Never be mean-spirited or punch down. Humor should be inclusive.
- If a joke doesn't land, pivot — don't double down on the same bit.

You're performing live. Every message is a chance to get a laugh. Make it count."""


def get_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def fetch_unexported(db_path: str) -> list[dict]:
    """Fetch all interactions with feedback that haven't been exported yet."""
    db = get_db(db_path)
    rows = db.execute("""
        SELECT id, session_id, timestamp, user_message, assistant_message,
               model, adapter_id, feedback
        FROM interactions
        WHERE feedback IS NOT NULL AND exported = 0
        ORDER BY timestamp ASC
    """).fetchall()
    db.close()
    return [dict(row) for row in rows]


def build_training_record(interaction: dict, context: list[dict]) -> dict:
    """Convert an interaction into a training-ready record.

    Format matches what the verifiers environment expects:
      - question: the prompt (as a formatted string or the user message)
      - answer: the target response
      - info: metadata including reward signal
    """
    # Build the prompt as the conversation context + current question
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Add prior context from same session (up to 4 previous turns)
    for ctx in context[-4:]:
        messages.append({"role": "user", "content": ctx["user_message"]})
        messages.append({"role": "assistant", "content": ctx["assistant_message"]})

    # Add the actual user message
    messages.append({"role": "user", "content": interaction["user_message"]})

    # The reward: 1.0 if funny, 0.0 if not
    reward = 1.0 if interaction["feedback"] == 1 else 0.0

    return {
        "question": interaction["user_message"],
        "answer": interaction["assistant_message"],
        "prompt": messages,
        "info": {
            "interaction_id": interaction["id"],
            "session_id": interaction["session_id"],
            "timestamp": interaction["timestamp"],
            "model": interaction["model"],
            "adapter_id": interaction["adapter_id"],
            "human_reward": reward,
            "feedback": "funny" if interaction["feedback"] == 1 else "not_funny",
        },
    }


def mark_as_exported(db_path: str, interaction_ids: list[str]):
    """Mark interactions as exported in the database."""
    db = get_db(db_path)
    placeholders = ",".join(["?"] * len(interaction_ids))
    db.execute(
        f"UPDATE interactions SET exported = 1 WHERE id IN ({placeholders})",
        interaction_ids,
    )
    db.commit()
    db.close()


def export_batch(
    db_path: str,
    output_path: str | None = None,
    min_batch_size: int = 10,
    mark_exported: bool = True,
) -> str | None:
    """Export a batch of training data.

    Returns the output file path, or None if batch was too small.
    """
    interactions = fetch_unexported(db_path)

    if len(interactions) < min_batch_size:
        print(
            f"Only {len(interactions)} unexported interactions "
            f"(need {min_batch_size}). Skipping export."
        )
        return None

    # Group by session for context building
    sessions: dict[str, list[dict]] = {}
    for ix in interactions:
        sid = ix["session_id"]
        if sid not in sessions:
            sessions[sid] = []
        sessions[sid].append(ix)

    # Build training records with conversation context
    records = []
    for session_id, session_interactions in sessions.items():
        for i, interaction in enumerate(session_interactions):
            context = session_interactions[:i]  # prior messages in session
            record = build_training_record(interaction, context)
            records.append(record)

    # Determine output path
    if output_path is None:
        DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        output_path = str(DEFAULT_OUTPUT_DIR / f"batch_{timestamp}.jsonl")

    # Write JSONL
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with open(output, "w") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")

    # Also write a latest.jsonl symlink/copy for the environment to find easily
    latest_path = output.parent / "latest.jsonl"
    if latest_path.exists() or latest_path.is_symlink():
        latest_path.unlink()
    # Use relative symlink
    try:
        latest_path.symlink_to(output.name)
    except OSError:
        # Fallback: just copy
        import shutil
        shutil.copy2(output, latest_path)

    print(f"Exported {len(records)} training records to {output}")
    print(f"  Sessions: {len(sessions)}")
    funny_count = sum(1 for r in records if r["info"]["human_reward"] == 1.0)
    print(f"  Funny: {funny_count} ({funny_count/len(records)*100:.1f}%)")
    print(f"  Not funny: {len(records) - funny_count}")

    # Mark as exported
    if mark_exported:
        ids = [ix["id"] for ix in interactions]
        mark_as_exported(db_path, ids)
        print(f"  Marked {len(ids)} interactions as exported")

    return str(output)


def main():
    parser = argparse.ArgumentParser(description="Export LaughLoop training data")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="Path to SQLite database")
    parser.add_argument("--output", "-o", default=None, help="Output JSONL file path")
    parser.add_argument(
        "--min-batch-size", type=int, default=10,
        help="Minimum interactions needed to export"
    )
    parser.add_argument(
        "--no-mark", action="store_true",
        help="Don't mark interactions as exported (useful for testing)"
    )
    args = parser.parse_args()

    if not Path(args.db).exists():
        print(f"Database not found: {args.db}")
        print("Start the backend first to create the database.")
        return

    result = export_batch(
        db_path=args.db,
        output_path=args.output,
        min_batch_size=args.min_batch_size,
        mark_exported=not args.no_mark,
    )

    if result:
        print(f"\nBatch ready for training: {result}")
    else:
        print("\nNo batch exported. Collect more feedback first.")


if __name__ == "__main__":
    main()
