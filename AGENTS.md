# AGENTS.md

## Project Overview

LaughLoop is an online reinforcement learning demo: a chat app where the AI tries to be funny, users give feedback (Haha or Meh), and that feedback automatically triggers RL training via the Prime Intellect platform. The model gets funnier over time without any manual intervention.

The system is a fully automated loop: **Serve -> Collect -> Export -> Train -> Deploy -> Eval -> Repeat**.

## Repository Structure

```
laughloop/
  app/
    backend/
      server.py              # FastAPI: all endpoints + auto-pipeline + eval runner
      requirements.txt       # Python dependencies (fastapi, openai, httpx, boto3)
      pyproject.toml         # Package metadata (used by Vercel build)
      vercel.json            # Vercel serverless routing + CORS headers
      logs/                  # Local JSONL logs (gitignored, only used in local dev)
    frontend/
      src/
        app/
          page.tsx           # Chat page: split-panel with chat + log viewer + pipeline
          evals/page.tsx     # Eval plots: 2x2 grid of LineCharts (recharts)
          layout.tsx         # Root layout with fonts + metadata
          globals.css        # Tailwind v4 + CSS custom properties
        components/
          header.tsx         # Shared nav header (Chat | Evals links)
          chat-input.tsx     # Message input box
          chat-message.tsx   # Individual chat bubble
          haha-button.tsx    # Haha/Meh feedback buttons
          empty-state.tsx    # Empty chat state
          typing-indicator.tsx
          stats-bar.tsx      # Feedback stats display
          log-viewer.tsx     # Interaction log table
          pipeline-panel.tsx # Training pipeline status panel
        lib/
          api.ts             # API client: all fetch calls + TypeScript interfaces
      next.config.ts         # Rewrites /api to localhost:8000 in local dev
      package.json           # next, react, recharts, tailwind, typescript
  pipeline/
    export_batch.py          # Export interactions -> JSONL training batches
    seed_data.py             # Generate synthetic test data for pipeline testing
  environments/
    laughloop_reward/
      laughloop_reward.py    # Verifiers RL environment (human feedback as reward)
      pyproject.toml         # Environment package metadata
  configs/
    rl.toml                  # RL training config for prime rl run
  scripts/
    loop.sh                  # Manual orchestrator (export -> train -> deploy)
  data/
    batches/                 # Exported JSONL training batches (gitignored)
  .env.example               # All environment variables with descriptions
  AGENTS.md                  # This file: detailed agent guide
  CLAUDE.md                  # Quick reference for AI agents
  README.md                  # Project overview + setup instructions
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
# Backend
pip install -r app/backend/requirements.txt

# Frontend
cd app/frontend && npm install
```

### Environment Variables

Copy `.env.example` to `.env` and fill in:

```bash
cp .env.example .env
```

Required variables:
- `PRIME_API_KEY` - Prime Intellect API key (get from https://app.primeintellect.ai/dashboard/tokens)
- `PRIME_TEAM_ID` - Team ID (find at Team Profile page, required for team accounts)

Optional for local dev:
- `OPENAI_API_KEY` - For the judge model in the verifiers environment
- `LAUGHLOOP_ADAPTER_ID` - Set after first training run to serve with the trained adapter

Required for deployment (Vercel + R2):
- `R2_ACCOUNT_ID` - Cloudflare account ID
- `R2_ACCESS_KEY_ID` - R2 S3-compatible access key
- `R2_SECRET_ACCESS_KEY` - R2 S3-compatible secret key
- `R2_BUCKET_NAME` - defaults to `laughloop`
- `NEXT_PUBLIC_API_URL` - Backend URL for frontend (e.g. `https://laughloop-backend.vercel.app`)

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

# Pipeline status
curl http://localhost:8000/pipeline

# Eval results
curl http://localhost:8000/evals

# Trigger eval run manually
curl -X POST http://localhost:8000/evals/run?model_version=0
```

### 2. Frontend

```bash
cd app/frontend
npm run dev
# Starts on http://localhost:3000
```

In local dev, `next.config.ts` proxies `/api/*` to `http://localhost:8000/*` so the frontend works without setting `NEXT_PUBLIC_API_URL`.

Two pages:
- `/` - Chat page with split-panel layout (chat, log viewer, pipeline panel)
- `/evals` - Eval plots page with 2x2 grid of performance charts

### 3. Seed Test Data (optional)

```bash
python pipeline/seed_data.py --count 100
```

This creates synthetic interactions with feedback for testing the pipeline.

## Key Integration Points

### Frontend -> Backend

- `api.ts` defines all fetch calls and TypeScript interfaces
- `API_BASE` is set from `NEXT_PUBLIC_API_URL` env var, or falls back to `/api` (proxied)
- Frontend polls `/pipeline` and `/evals` every 10 seconds for live updates
- CORS is open (`allow_origins=["*"]`) for development

### Backend Storage (Local vs R2)

- When `R2_ACCOUNT_ID` + `R2_ACCESS_KEY_ID` + `R2_SECRET_ACCESS_KEY` are set AND boto3 is installed, the backend uses R2
- Otherwise, it falls back to local JSONL files in `app/backend/logs/`
- R2 keys used:
  - `logs/interactions.jsonl` - interaction log
  - `pipeline/state.json` - training pipeline state (survives Vercel cold starts)
  - `evals/results.json` - eval results
  - `batches/<filename>.jsonl` - exported training batches

### Backend Auto-Pipeline

The pipeline is fully automated inside `server.py`:

1. **Feedback threshold check**: On each `/feedback` POST, checks if labeled count >= `LAUGHLOOP_MIN_BATCH` (default 20)
2. **Inline export**: `_inline_export()` converts interactions to training JSONL (no external script needed)
3. **Training via API**: `_start_training_run_api()` calls `POST /api/v1/training/runs` on Prime
4. **Run monitoring**: Background task (`_watch_run`) or lazy-polling (`_lazy_poll_run`) tracks progress
5. **Auto-deploy**: `_auto_deploy_adapter()` finds the adapter from the completed run and deploys it
6. **Hot-swap**: `ADAPTER_ID` global is updated; next chat uses the new adapter immediately
7. **Auto-eval**: After deploy, `_start_eval_watcher()` or `_submit_evals_serverless()` triggers hosted evals

### Backend Eval System

After adapter deployment, evals are auto-triggered on 4 environments:
- `primeintellect/aime2026`, `primeintellect/gsm8k`, `primeintellect/wordle`, `prime/tau2-synth`

Flow:
1. Resolve environment slugs to IDs via `GET /api/v1/environmentshub/{owner}/{name}/@latest`
2. Submit hosted evals via `POST /api/v1/hosted-evaluations`
3. Poll `GET /api/v1/evaluations/{eval_id}` until complete
4. Extract scores from metrics or sample averages
5. Store results in R2 (`evals/results.json`)

Configuration (in `server.py`):
- `EVAL_NUM_EXAMPLES = 10`
- `EVAL_ROLLOUTS_PER_EXAMPLE = 3`
- `EVAL_POLL_INTERVAL = 15` seconds
- `EVAL_MAX_POLLS = 120` (~30 min timeout)

### Pipeline -> Environment -> Training

- `export_batch.py` reads from JSONL log, outputs to `data/batches/`
- Each record has: `question`, `answer`, `prompt` (full message list), `info` (with `human_reward`)
- `laughloop_reward.py` loads batches and uses human feedback as the reward signal
- `configs/rl.toml` references the environment by name: `prime/laughloop-reward`
- Training produces adapters uploaded to the Prime platform
- Sample multiplier (`LAUGHLOOP_SAMPLE_MULTIPLIER`, default 5) duplicates each interaction to reach effective batch sizes

### Training -> Deployment -> Inference

- Training produces LoRA adapters uploaded to Prime
- Backend auto-deploys via `POST /api/v1/deployments/adapters/{adapter_id}/deploy`
- Polls deployment status until DEPLOYED
- Inference uses `model="BaseModel:adapter_id"` format (e.g. `Qwen/Qwen3-4B-Instruct-2507:abc123`)
- See https://docs.primeintellect.ai/inference/adapter-deployments for details

## Deployment

### Vercel Backend

- `app/backend/vercel.json` routes all requests to `server.py`
- Vercel builds using `@vercel/python` builder
- `pyproject.toml` lists dependencies for the Vercel build
- `requirements.txt` is the canonical dependency list

### Vercel Frontend

- Standard Next.js deployment
- `NEXT_PUBLIC_API_URL` must be set to the backend URL (baked at build time)
- Without it, the frontend tries `/api` which only works with the local dev proxy

### Serverless Considerations

- No background tasks on Vercel - everything uses lazy-polling
- State is persisted to R2 so it survives cold starts
- `_load_pipeline_state()` is called at the start of relevant endpoints to reload from R2
- Training monitoring, deployment polling, and eval polling all use the lazy-poll pattern:
  - State is checked/updated on each GET request
  - If status is "running"/"training"/"deploying", one poll cycle runs per request

## Common Issues

- **401 on inference**: Check `PRIME_API_KEY` is valid. Run `prime login` to refresh. Verify the model exists with `prime inference models`.
- **401 on platform API (evals)**: The eval endpoints may need different API key permissions. Regenerate at https://app.primeintellect.ai/dashboard/tokens.
- **Training data not found**: Run `POST /pipeline/export` or seed data with `pipeline/seed_data.py`.
- **Environment not found during training**: Run `prime env install laughloop-reward --path ./environments`.
- **Frontend shows "Connection error"**: Backend isn't running, or `NEXT_PUBLIC_API_URL` isn't set on the deployed frontend.
- **Pipeline state disappears on Vercel**: R2 credentials may be wrong. Check `GET /health` shows `"storage": "r2"`.
- **308 redirects from backend**: Vercel adds trailing slashes. `vercel.json` has `"trailingSlash": false` and the frontend strips trailing slashes from `API_BASE`.
- **CORS errors**: Backend has permissive CORS (`allow_origins=["*"]`). `vercel.json` also adds CORS headers as a fallback.

## Code Conventions

- **Python**: Standard formatting, type hints where practical, `pathlib.Path` for all file paths
- **TypeScript**: Strict mode, all API responses have interfaces in `api.ts`
- **Frontend**: App Router (no pages/ directory), Tailwind v4 with CSS custom properties for theming
- **Design**: Monochrome/minimalist. No gradients, no bright colors, no emojis in UI. Mono font throughout.
- **No pre-commit hooks** configured; add ruff if desired
- Environment variables read with `os.getenv()` with sensible defaults

## What May Need Work

- **Eval baseline scores**: Real baseline scores for Qwen3-4B have not been posted yet (blocked on platform API auth). Once the API key has platform permissions, trigger `POST /evals/run?model_version=0` to run baseline evals.
- **Score extraction**: `_extract_eval_score()` guesses metric keys (`avg_score`, `mean_score`, `score`, `accuracy`, `reward`). Verify against actual API response once evals run successfully.
- **Environment resolution for evals**: The `_resolve_environment_id()` function calls a specific API endpoint. If the API schema changes, this needs updating.
- **W&B integration**: The `rl.toml` has commented-out W&B config. Uncomment and set entity/project to enable training dashboards.
- **Authentication**: No user auth on any endpoints. All APIs are open. Add auth if this goes beyond demo usage.
