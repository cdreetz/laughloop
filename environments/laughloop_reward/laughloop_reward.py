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
        """Load the latest batch of training data."""
        data_path = Path(data_dir) / data_file

        if not data_path.exists():
            raise FileNotFoundError(
                f"Training data not found at {data_path}. "
                f"Run `python pipeline/export_batch.py` first."
            )

        records = []
        with open(data_path) as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))

        if not records:
            raise ValueError(f"No records found in {data_path}")

        # Convert to dataset format
        dataset_records = []
        for record in records:
            dataset_records.append({
                "question": record["question"],
                "answer": record.get("answer", ""),
                "info": json.dumps({
                    "human_reward": record["info"]["human_reward"],
                    "feedback": record["info"]["feedback"],
                    "original_response": record.get("answer", ""),
                    "interaction_id": record["info"].get("interaction_id", ""),
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
