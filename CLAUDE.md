# CLAUDE.md

Before beginning work in this repository, read `AGENTS.md` and follow all guidance there.

## Quick Context

This is **LaughLoop** — a continual learning MVP. A chat app where the AI tries to be funny, users give 😂/😐 feedback, and that feedback trains the model via RL to get funnier over time.

The codebase is a complete end-to-end loop: chat app → feedback logging → data export → RL training → adapter deployment → serve with new weights → repeat.

## Priority Tasks

If you're picking this up to finish and test:

1. **Verify the backend runs** — `cd app/backend && python server.py` — hit `/health` to confirm
2. **Start the frontend** — `cd app/frontend && npm install && npm run dev`
3. **Seed test data** — `python pipeline/seed_data.py --count 100`
4. **Test the export pipeline** — `python pipeline/export_batch.py` — confirm `data/batches/latest.jsonl` exists and is valid JSONL
5. **Install the verifiers environment** — `prime env install laughloop-reward --path ./environments`
6. **Run a test eval** — `prime eval run laughloop-reward -n 5 -r 1 -a '{"data_dir": "./data/batches"}'`
7. **Run RL training** — `prime rl run configs/rl.toml`
8. **Test deployment** — `python scripts/deploy_adapter.py`
9. **Run the full loop** — `bash scripts/loop.sh`

## Key Files to Know

- `app/backend/server.py` — The main application server. All API endpoints live here.
- `pipeline/export_batch.py` — Converts interaction logs to training JSONL. This is the bridge between serving and training.
- `environments/laughloop_reward/laughloop_reward.py` — The verifiers environment. This is what `prime rl run` loads. The reward signal comes from human feedback stored in the JSONL.
- `configs/rl.toml` — Training hyperparameters. Adjust `max_steps`, `batch_size`, `rollouts_per_example` here.
- `scripts/loop.sh` — The orchestrator. Read this to understand how all pieces connect.

## Environment Setup

```bash
# Required
export PRIME_API_KEY="..."

# Optional but recommended
export OPENAI_API_KEY="..."       # For judge model in training env
export LAUGHLOOP_ADAPTER_ID="..." # After first training run
```

Or copy `.env.example` to `.env`.

## Things That Need CLI Access

These operations require the `prime` CLI to be installed and authenticated:

- `prime env install ...` — Installing the verifiers environment
- `prime eval run ...` — Running evaluations
- `prime rl run ...` — Running RL training
- `prime rl models` — Checking available base models
- `prime deployments list` — Checking adapter status

All of these need a valid `PRIME_API_KEY`. Run `prime login` first.
