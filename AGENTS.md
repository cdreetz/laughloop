# AGENTS.md

## Project Overview

LaughLoop is a continual learning MVP: a chat app where the AI tries to be funny, users give feedback (😂 Haha or 😐 Meh), and that feedback trains the model via reinforcement learning to get funnier over time.

The system is an end-to-end loop: **Serve → Collect → Export → Train → Deploy → Repeat**.

## Repository Structure

```
laughloop/
├── app/
│   ├── backend/
│   │   ├── server.py              # FastAPI: /chat, /feedback, /stats, /health
│   │   ├── requirements.txt       # Backend Python dependencies
│   │   └── laughloop.db           # SQLite log database (created at runtime)
│   └── frontend/
│       └── App.jsx                # React chat UI with Haha/Meh feedback buttons
├── pipeline/
│   ├── export_batch.py            # Export logged interactions → JSONL training batches
│   └── seed_data.py               # Generate synthetic test data for pipeline testing
├── environments/
│   └── laughloop_reward/
│       ├── laughloop_reward.py    # Verifiers RL environment (loads JSONL, human reward)
│       ├── pyproject.toml         # Environment package metadata + dependencies
│       └── README.md              # Environment documentation
├── configs/
│   └── rl.toml                    # RL training config for `prime rl run`
├── scripts/
│   ├── deploy_adapter.py          # Deploy trained adapter via Prime API
│   └── loop.sh                    # Full orchestrator: export → train → deploy
├── data/
│   └── batches/                   # Exported JSONL training batches (gitignored)
├── logs/                          # Loop execution logs (gitignored)
├── pyproject.toml                 # Top-level project dependencies
├── .env.example                   # Environment variable template
├── .gitignore
└── README.md
```

## Setup Instructions

### Prerequisites

```bash
# Install uv (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install prime CLI
uv tool install prime

# Authenticate with Prime Intellect
prime login
```

### Install Dependencies

```bash
cd laughloop

# Install project dependencies
uv sync

# Or with pip
pip install -r app/backend/requirements.txt
pip install verifiers>=0.1.8 datasets openai
```

### Environment Variables

Copy `.env.example` to `.env` and fill in:

```bash
cp .env.example .env
```

Required variables:
- `PRIME_API_KEY` — Prime Intellect API key (get from https://app.primeintellect.ai/dashboard/tokens)
- `LAUGHLOOP_MODEL` — Model to serve chat with (default: `openai/gpt-4.1-mini`)
- `LAUGHLOOP_BASE_URL` — Inference API base URL (default: `https://api.pinference.ai/api/v1`)

Optional:
- `OPENAI_API_KEY` — For the judge model in the verifiers environment (improves training signal)
- `LAUGHLOOP_ADAPTER_ID` — Set after first training run to serve with the trained adapter

## Running Each Component

### 1. Backend Server

```bash
cd app/backend
python server.py
# Starts on http://localhost:8000
```

Test endpoints:
```bash
# Health check
curl http://localhost:8000/health

# Send a chat message
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Tell me a joke"}'

# Submit feedback (use the interaction id from the chat response)
curl -X POST http://localhost:8000/feedback \
  -H "Content-Type: application/json" \
  -d '{"interaction_id": "<id>", "funny": true}'

# Check stats
curl http://localhost:8000/stats
```

### 2. Frontend

The frontend is a React component (`App.jsx`). For local development, serve it however you prefer. It expects the backend at `http://localhost:8000`. The `API_BASE` constant at the top of `App.jsx` controls this.

### 3. Seed Test Data

To test the pipeline without real user interactions:

```bash
python pipeline/seed_data.py --count 100
```

This populates the SQLite database with synthetic interactions that have feedback attached.

### 4. Export Training Data

```bash
python pipeline/export_batch.py
# Exports to data/batches/batch_<timestamp>.jsonl
# Creates data/batches/latest.jsonl symlink
```

Options:
- `--min-batch-size 10` — Minimum interactions needed to trigger export
- `--no-mark` — Don't mark interactions as exported (for testing)
- `--output path/to/file.jsonl` — Custom output path

### 5. Install the Verifiers Environment

```bash
prime env install laughloop-reward --path ./environments
```

Verify installation:
```bash
python -c "from laughloop_reward import load_environment; env = load_environment(); print('OK')"
```

### 6. Run RL Training

```bash
prime rl run configs/rl.toml
```

This requires:
- Exported training data at `data/batches/latest.jsonl`
- The `laughloop-reward` environment installed
- Valid `PRIME_API_KEY`

### 7. Deploy Trained Adapter

```bash
python scripts/deploy_adapter.py
```

Or for a specific run:
```bash
python scripts/deploy_adapter.py --run-id <run_id>
```

### 8. Full Loop

```bash
bash scripts/loop.sh
```

## Testing the Full Pipeline

The recommended test sequence:

```bash
# 1. Start the backend
python app/backend/server.py &

# 2. Seed synthetic data
python pipeline/seed_data.py --count 100

# 3. Export a training batch
python pipeline/export_batch.py --min-batch-size 10

# 4. Verify the export
cat data/batches/latest.jsonl | head -3 | python -m json.tool

# 5. Install the environment
prime env install laughloop-reward --path ./environments

# 6. Run a quick eval to verify the environment works
prime eval run laughloop-reward -n 5 -r 1 --path ./environments \
  -a '{"data_dir": "./data/batches", "data_file": "latest.jsonl"}'

# 7. Run RL training (requires Prime account with training access)
prime rl run configs/rl.toml

# 8. Deploy the adapter
python scripts/deploy_adapter.py
```

## Key Integration Points

### Backend ↔ Frontend
- Frontend calls `POST /chat` and `POST /feedback`
- `API_BASE` in `App.jsx` must match backend address
- CORS is open (`allow_origins=["*"]`) for development

### Backend ↔ Database
- SQLite at `app/backend/laughloop.db`
- Created automatically on first backend start
- Schema: `interactions` table with columns: id, session_id, timestamp, user_message, assistant_message, model, adapter_id, feedback, feedback_timestamp, exported

### Pipeline ↔ Database
- `export_batch.py` reads from the same SQLite database
- Reads rows where `feedback IS NOT NULL AND exported = 0`
- Marks rows as `exported = 1` after successful export
- `--db` flag to point at a different database path

### Pipeline ↔ Environment
- Pipeline outputs JSONL to `data/batches/`
- Environment loads from `data/batches/latest.jsonl` by default
- Each JSONL record has: `question`, `answer`, `prompt` (full message list), `info` (with `human_reward`)
- The `data_dir` and `data_file` environment args control the path

### Environment ↔ Training
- The `configs/rl.toml` references the environment by name: `laughloop-reward`
- Environment args are passed via `args = { data_dir = "...", data_file = "..." }` in the TOML
- The environment must be installed before training: `prime env install laughloop-reward --path ./environments`

### Training ↔ Deployment
- `prime rl run` produces adapters uploaded to the Prime platform
- `deploy_adapter.py` finds the latest adapter, deploys it, and writes the adapter ID to `app/backend/.adapter_config`
- Backend reads `LAUGHLOOP_ADAPTER_ID` env var and passes it as `lora_id` in the inference call

## Common Issues

- **"Training data not found"** — Run `python pipeline/export_batch.py` first, or seed data with `pipeline/seed_data.py`
- **"No API key configured"** — Set `PRIME_API_KEY` in your environment or `.env` file, then `prime login`
- **Backend can't reach inference** — Check `LAUGHLOOP_BASE_URL` and that your API key has inference access
- **Environment not found during training** — Run `prime env install laughloop-reward --path ./environments`
- **CORS errors in frontend** — Backend must be running; check the `API_BASE` constant in `App.jsx`

## What May Need Finishing

- The React frontend (`App.jsx`) needs to be served — either integrate into a build system (Vite, Next.js) or serve as a standalone HTML page
- The `LAUGHLOOP_ADAPTER_ID` update after deployment currently writes to a file; the backend needs a restart or a hot-reload mechanism to pick it up
- The `rl.toml` config uses `Qwen/Qwen3-0.6B` as the base model — verify this is available on your Prime account with `prime rl models`
- For production, replace SQLite with a proper database and add authentication to the API
- The judge model component in the environment requires an `OPENAI_API_KEY` — it's optional but improves training signal
- `loop.sh` is designed for cron — test it end-to-end before scheduling

## Code Style

- Python: standard formatting, type hints where practical
- No pre-commit hooks configured yet; add ruff if desired
- All paths use `Path` from pathlib where possible
- Environment variables are read with `os.getenv()` with sensible defaults
