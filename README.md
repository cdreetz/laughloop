# LaughLoop

**Online reinforcement learning demo -- an AI chat app that improves from human feedback in real time.**

Users chat with an AI that tries to be funny. They click "Haha" on responses they like. That feedback automatically triggers RL training, deploys a new adapter, and the model gets funnier. The loop runs continuously without manual intervention.

**Live demo:** [laughloop-frontend.vercel.app](https://laughloop-frontend.vercel.app)

## Architecture

```
User --> Next.js Frontend --> FastAPI Backend --> JSONL Log (R2 or local)
              |                     |
              |                     |-- POST /chat (inference via Prime)
              |                     |-- POST /feedback (haha/meh)
              |                     |-- GET /pipeline (training status)
              |                     '-- GET /evals (eval scores)
              |                     |
              |               [Auto-pipeline]
              |                     |
              |         +-----------+-----------+
              |         |  20 labeled? Export   |
              |         |  -> Train via Prime RL|
              |         |  -> Deploy adapter    |
              |         |  -> Hot-swap model    |
              |         |  -> Run evals         |
              |         +-----------------------+
              |
              |-- /       Chat page (split-panel: chat + log viewer + pipeline)
              '-- /evals  Eval plots (2x2 grid: 4 environments over time)
```

## Tech Stack

| Layer | Tech | Notes |
|-------|------|-------|
| Frontend | Next.js 16, TypeScript, Tailwind v4, Recharts | App Router, monochrome design |
| Backend | FastAPI, Python 3.10+ | Single `server.py`, deploys to Vercel |
| Storage | JSONL logs, Cloudflare R2 (S3-compatible) | Falls back to local files |
| Training | Prime Intellect RL platform | `prime rl run` with custom verifiers environment |
| Inference | Prime Inference API (`api.pinference.ai`) | Qwen3-4B with LoRA adapter hot-swap |
| Evals | Prime Hosted Evaluations API | 4 environments, auto-triggered after deploy |

## Repository Structure

```
laughloop/
├── app/
│   ├── backend/
│   │   ├── server.py              # FastAPI backend (all endpoints + auto-pipeline)
│   │   ├── requirements.txt       # Python dependencies
│   │   ├── pyproject.toml         # Package metadata for Vercel
│   │   ├── vercel.json            # Vercel serverless config
│   │   └── logs/                  # Local JSONL logs (gitignored)
│   └── frontend/
│       ├── src/
│       │   ├── app/
│       │   │   ├── page.tsx       # Chat page (main UI)
│       │   │   └── evals/page.tsx # Eval plots page
│       │   ├── components/        # UI components (header, chat, pipeline panel, etc.)
│       │   └── lib/api.ts         # API client with TypeScript interfaces
│       ├── next.config.ts         # Rewrites for local dev proxy
│       └── package.json
├── pipeline/
│   ├── export_batch.py            # Export interactions -> JSONL training batches
│   └── seed_data.py               # Generate synthetic test data
├── environments/
│   └── laughloop_reward/
│       ├── laughloop_reward.py    # Verifiers RL environment (human feedback as reward)
│       └── pyproject.toml
├── configs/
│   └── rl.toml                    # RL training config for prime rl run
├── scripts/
│   └── loop.sh                    # Manual orchestrator (export -> train -> deploy)
├── .env.example                   # All environment variables documented
├── AGENTS.md                      # Detailed agent onboarding guide
└── CLAUDE.md                      # Quick reference for AI agents
```

## Quick Start (Local Dev)

### Prerequisites

```bash
# Python 3.10+
pip install -r app/backend/requirements.txt

# Node.js 18+
cd app/frontend && npm install

# Prime CLI (for training)
uv tool install prime
prime login
```

### Environment Variables

```bash
cp .env.example .env
# Required:
#   PRIME_API_KEY       - from https://app.primeintellect.ai/dashboard/tokens
#   PRIME_TEAM_ID       - from Team Profile page (if using team account)
# Optional:
#   OPENAI_API_KEY      - for judge model in training environment
#   R2_ACCOUNT_ID       - Cloudflare R2 (for deployed/serverless mode)
#   R2_ACCESS_KEY_ID    - R2 S3-compatible credentials
#   R2_SECRET_ACCESS_KEY
```

### Run Locally

```bash
# Terminal 1: Backend
cd app/backend
python server.py
# Starts on http://localhost:8000

# Terminal 2: Frontend
cd app/frontend
npm run dev
# Starts on http://localhost:3000 (proxies /api to :8000 automatically)
```

### Verify

```bash
curl http://localhost:8000/health
# {"status": "ok", "model": "Qwen/Qwen3-4B-Instruct-2507", "storage": "local", ...}
```

## Deployment (Vercel + R2)

Both frontend and backend deploy to Vercel. Storage uses Cloudflare R2.

### Backend (Vercel Python)

1. Create a Vercel project pointing to `app/backend`
2. Set environment variables:
   - `PRIME_API_KEY`, `PRIME_TEAM_ID`
   - `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`
   - `R2_BUCKET_NAME=laughloop`
3. Deploy. `vercel.json` routes all requests to `server.py`

### Frontend (Vercel Next.js)

1. Create a Vercel project pointing to `app/frontend`
2. Set `NEXT_PUBLIC_API_URL` to the backend URL (e.g. `https://laughloop-backend.vercel.app`)
3. Deploy. Standard Next.js build.

### R2 Setup

Create a Cloudflare R2 bucket named `laughloop`. Generate S3-compatible API tokens at:
**R2 Object Storage > Manage R2 API Tokens > Create API Token**

This gives you an Access Key ID and Secret Access Key (different from regular Cloudflare API tokens).

## How the Auto-Pipeline Works

The backend automatically runs the full training loop without manual intervention:

1. **Collect feedback** - Users chat and click Haha/Meh. Each interaction is logged.
2. **Auto-trigger at threshold** - When 20+ labeled interactions accumulate, the pipeline auto-triggers.
3. **Export** - Interactions are exported to a JSONL training batch (inline, no CLI needed).
4. **Train** - An RL training run starts on Prime platform via API.
5. **Monitor** - Background task (local) or lazy-polling (serverless) tracks training progress.
6. **Deploy** - When training completes, the latest adapter is auto-deployed via Prime API.
7. **Hot-swap** - The adapter ID is updated in-memory; new chat requests use the fine-tuned model immediately.
8. **Auto-eval** - After deployment, hosted evaluations run on 4 environments via Prime API. Results are stored and displayed on the `/evals` page.

### Serverless vs Local Dev

| Feature | Local Dev | Vercel (Serverless) |
|---------|-----------|---------------------|
| Training monitor | Background asyncio task | Lazy-poll on `/pipeline` requests |
| Eval runner | Background task polls until done | Submit + lazy-poll on `/evals` requests |
| State persistence | In-memory (lost on restart) | R2 (`pipeline/state.json`) |
| Log storage | Local JSONL files | R2 object store |

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/chat` | Send message, get AI response |
| POST | `/feedback` | Submit Haha (funny=true) or Meh (funny=false) |
| GET | `/stats` | Feedback statistics (total, haha rate, etc.) |
| GET | `/interactions` | All logged interactions (for log viewer) |
| GET | `/pipeline` | Training pipeline status (batches, run, model version) |
| POST | `/pipeline/export` | Manually trigger batch export |
| POST | `/pipeline/train` | Manually start training run |
| POST | `/pipeline/deploy` | Manually deploy latest adapter |
| GET | `/evals` | Eval results for all environments |
| POST | `/evals` | Submit eval results manually |
| POST | `/evals/run` | Manually trigger eval run |
| GET | `/health` | Health check with model info |

## Eval Environments

The backend auto-runs evaluations on these 4 environments after each adapter deployment:

| Environment | What it tests |
|-------------|---------------|
| `primeintellect/aime2026` | Math reasoning |
| `primeintellect/gsm8k` | Grade school math |
| `primeintellect/wordle` | Word puzzle solving |
| `prime/tau2-synth` | Synthetic reasoning |

Results are displayed on the `/evals` page as a 2x2 grid of line charts with baseline (dotted) and fine-tuned (solid) performance over training iterations.

## Known Issues

- **Prime platform API auth for evals**: The eval runner calls `/api/v1/environmentshub/` and `/api/v1/hosted-evaluations`. These may return 401 depending on API key permissions. The code handles this gracefully (logs warnings, skips evals). If evals aren't running, regenerate the API key with platform permissions.
- **Vercel cold starts**: Pipeline state is persisted to R2 to survive serverless cold starts. If state seems stale, hit `GET /pipeline` to trigger a lazy-poll refresh.
- **Training environment**: `prime/laughloop-reward` must be installed on the Prime platform for training to work. Run `prime env install laughloop-reward --path ./environments`.

## Development Notes

- **Base model**: `Qwen/Qwen3-4B-Instruct-2507` (configurable via `LAUGHLOOP_MODEL`)
- **Inference**: Via Prime Inference API (`api.pinference.ai`), OpenAI-compatible
- **Training config**: 50 steps, batch size 64, 4 rollouts/example (see `configs/rl.toml`)
- **Feedback threshold**: 20 labeled interactions trigger auto-training (`LAUGHLOOP_MIN_BATCH`)
- **Sample multiplier**: Each interaction duplicated 5x in training batches (`LAUGHLOOP_SAMPLE_MULTIPLIER`)
- **Frontend**: Monochrome split-panel design, no colors except minimal accents
- All Python paths use `pathlib.Path`; env vars use `os.getenv()` with defaults
