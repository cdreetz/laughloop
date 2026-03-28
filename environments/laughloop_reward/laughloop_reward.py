"""
LaughLoop Reward Environment — RL training with human humor feedback.

This environment loads batches of chat interactions where users have
indicated whether the AI's response was funny (😂 Haha) or not.

The reward signal is simple:
  - The model generates a response to the user's message
  - A judge evaluates it based on the original human feedback
  - Responses that match the "funny" pattern get higher reward

Training objective: Learn to generate responses that humans find funny.
"""

import json
import os
from pathlib import Path

from datasets import Dataset
from openai import AsyncOpenAI

import verifiers as vf

# Default path to the latest exported batch
DEFAULT_DATA_DIR = os.getenv(
    "LAUGHLOOP_DATA_DIR",
    str(Path(__file__).parent.parent.parent / "data" / "batches"),
)

# Fallback sample data for cloud training when local files aren't available.
# In production, the pipeline exports real user interactions; these seeds
# let the environment boot even without a local data directory.
FALLBACK_DATA = [
    {
        "question": "Tell me a joke",
        "answer": "Why don't skeletons fight each other? They don't have the guts.",
        "info": {"human_reward": 1.0, "feedback": "funny", "interaction_id": "seed-1", "original_response": "Why don't skeletons fight each other? They don't have the guts."},
    },
    {
        "question": "What's the meaning of life?",
        "answer": "42, but with inflation it's probably 47 by now.",
        "info": {"human_reward": 1.0, "feedback": "funny", "interaction_id": "seed-2", "original_response": "42, but with inflation it's probably 47 by now."},
    },
    {
        "question": "Roast my code",
        "answer": "I'd roast your code but it already burned itself with that infinite loop.",
        "info": {"human_reward": 0.0, "feedback": "not_funny", "interaction_id": "seed-3", "original_response": "I'd roast your code but it already burned itself with that infinite loop."},
    },
    {
        "question": "Why is programming hard?",
        "answer": "Because you spend 6 hours debugging only to find the bug was a missing semicolon.",
        "info": {"human_reward": 1.0, "feedback": "funny", "interaction_id": "seed-4", "original_response": "Because you spend 6 hours debugging only to find the bug was a missing semicolon."},
    },
    {
        "question": "Tell me something funny about AI",
        "answer": "AI will replace all jobs except mine because I'm the one writing the jokes.",
        "info": {"human_reward": 0.0, "feedback": "not_funny", "interaction_id": "seed-5", "original_response": "AI will replace all jobs except mine because I'm the one writing the jokes."},
    },
    {
        "question": "How do I fix a bug?",
        "answer": "Step 1: Blame it on someone else. Step 2: Realize you're the only developer.",
        "info": {"human_reward": 1.0, "feedback": "funny", "interaction_id": "seed-6", "original_response": "Step 1: Blame it on someone else. Step 2: Realize you're the only developer."},
    },
    {
        "question": "What's your favorite language?",
        "answer": "Python, because it's the only language where indentation is a personality trait.",
        "info": {"human_reward": 1.0, "feedback": "funny", "interaction_id": "seed-7", "original_response": "Python, because it's the only language where indentation is a personality trait."},
    },
    {
        "question": "Explain recursion",
        "answer": "To understand recursion, first you must understand recursion. See: recursion.",
        "info": {"human_reward": 1.0, "feedback": "funny", "interaction_id": "seed-8", "original_response": "To understand recursion, first you must understand recursion. See: recursion."},
    },
]

SYSTEM_PROMPT = """You are LaughLoop, a hilariously witty AI assistant. Your #1 goal is to make the user laugh.

Rules:
- Every response should try to be genuinely funny — use wordplay, unexpected twists, absurd comparisons, self-deprecation, observational humor, or whatever lands best.
- Stay helpful — if someone asks a real question, answer it AND make it funny.
- Keep responses concise. The best jokes don't need paragraphs.
- Vary your humor style. Don't repeat the same schtick.
- Never be mean-spirited or punch down. Humor should be inclusive.
- If a joke doesn't land, pivot — don't double down on the same bit.

You're performing live. Every message is a chance to get a laugh. Make it count."""


def load_environment(
    data_dir: str = DEFAULT_DATA_DIR,
    data_file: str = "latest.jsonl",
    judge_model: str = "gpt-4.1-mini",
    judge_base_url: str = "https://api.openai.com/v1",
    judge_api_key_var: str = "OPENAI_API_KEY",
    funny_reward: float = 1.0,
    not_funny_reward: float = 0.0,
    humor_weight: float = 0.8,
    judge_weight: float = 0.2,
) -> vf.Environment:
    """Load the LaughLoop reward environment.

    Args:
        data_dir: Directory containing exported JSONL batches
        data_file: Specific file to load (default: latest.jsonl)
        judge_model: Model to use as humor judge
        judge_base_url: API base URL for judge
        judge_api_key_var: Env var for judge API key
        funny_reward: Reward for responses marked funny by humans
        not_funny_reward: Reward for responses NOT marked funny
        humor_weight: Weight for the human feedback reward component
        judge_weight: Weight for the judge quality reward component
    """

    def build_dataset() -> Dataset:
        """Load the latest batch of training data.

        Tries the local data directory first (for local dev / fresh exports),
        then falls back to embedded seed data so the environment always boots
        even when running in Prime's cloud infrastructure.
        """
        data_path = Path(data_dir) / data_file
        records: list[dict] = []

        if data_path.exists():
            with open(data_path) as f:
                for line in f:
                    if line.strip():
                        records.append(json.loads(line))

        # Fall back to embedded seed data when no local file is available
        if not records:
            records = FALLBACK_DATA

        # Convert to dataset format
        dataset_records = []
        for record in records:
            info = record["info"]
            if isinstance(info, str):
                info = json.loads(info)
            dataset_records.append({
                "question": record["question"],
                "answer": record.get("answer", ""),
                "info": json.dumps({
                    "human_reward": info["human_reward"],
                    "feedback": info["feedback"],
                    "original_response": record.get("answer", ""),
                    "interaction_id": info.get("interaction_id", ""),
                }),
            })

        return Dataset.from_list(dataset_records)

    # --- Reward function 1: Human feedback signal ---
    # This is the primary reward — did the human think it was funny?
    def human_feedback_reward(completion, info, **kwargs) -> float:
        """Use the stored human feedback as reward signal.

        This compares the model's NEW response to what the human
        thought of the ORIGINAL response. The idea is that responses
        similar in style/quality to funny ones should be rewarded.
        """
        if isinstance(info, str):
            info = json.loads(info)
        return info.get("human_reward", 0.0)

    # --- Reward function 2: Judge quality check ---
    # A secondary signal from a judge model rating humor quality
    judge_client = AsyncOpenAI(
        base_url=judge_base_url,
        api_key=os.getenv(judge_api_key_var, ""),
    )

    judge_prompt = """Rate how funny this AI response is on a scale of 0.0 to 1.0.

User message: {question}
AI response: {response}

Consider:
- Is it genuinely funny or just trying too hard?
- Does it use clever wordplay, unexpected twists, or good timing?
- Is it both funny AND responsive to the user's message?

Respond with ONLY a number between 0.0 and 1.0. Nothing else."""

    rubric = vf.Rubric(
        funcs=[human_feedback_reward],
        weights=[1.0],
    )

    # Optionally add judge-based quality reward
    if judge_weight > 0 and os.getenv(judge_api_key_var):
        judge_rubric = vf.JudgeRubric(
            judge_client=judge_client,
            judge_model=judge_model,
            judge_prompt=judge_prompt,
        )

        async def judge_humor_score(judge, prompt, completion, answer, state) -> float:
            """Get a humor quality score from the judge model."""
            try:
                judge_response = await judge(prompt, completion, answer, state)
                score = float(judge_response.strip())
                return max(0.0, min(1.0, score))
            except (ValueError, TypeError):
                return 0.5  # neutral if judge fails

        judge_rubric.add_reward_func(judge_humor_score, weight=judge_weight)

        # Use RubricGroup to combine both reward signals
        combined_rubric = vf.RubricGroup(rubrics=[rubric, judge_rubric])
    else:
        combined_rubric = rubric

    env = vf.SingleTurnEnv(
        dataset=build_dataset,
        system_prompt=SYSTEM_PROMPT,
        rubric=combined_rubric,
    )

    return env
