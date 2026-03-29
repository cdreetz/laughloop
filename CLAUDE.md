# CLAUDE.md

Before beginning work in this repository, read `AGENTS.md` and follow all guidance there.

## Quick Context

This is **LaughLoop** - an online reinforcement learning demo. A chat app where the AI tries to be funny, users give Haha/Meh feedback, and that feedback automatically triggers RL training via Prime Intellect to make the model funnier over time.

The entire pipeline is automated: feedback collection -> batch export -> RL training -> adapter deployment -> model hot-swap -> eval runs. No manual intervention needed.

## Quickstart

```bash
# Backend
cd app/backend && pip install -r requirements.txt && python server.py

# Frontend (separate terminal)
cd app/frontend && npm install && npm run dev
```

Backend: http://localhost:8000 | Frontend: http://localhost:3000

## Key Files

- `app/backend/server.py` - The entire backend. All API endpoints, auto-pipeline logic, eval runner, storage layer. This is ~1800 lines and is the heart of the application.
- `app/frontend/src/lib/api.ts` - All frontend API calls and TypeScript interfaces. Start here to understand the data model.
- `app/frontend/src/app/page.tsx` - Chat page (main UI).
- `app/frontend/src/app/evals/page.tsx` - Eval plots page (2x2 grid of performance charts).
- `app/frontend/src/components/pipeline-panel.tsx` - Training pipeline status UI.
- `configs/rl.toml` - Training hyperparameters.
- `environments/laughloop_reward/laughloop_reward.py` - Verifiers RL environment.
- `.env.example` - All environment variables documented.

## Environment Setup

```bash
# Required
export PRIME_API_KEY="..."
export PRIME_TEAM_ID="..."  # for team accounts

# Optional
export OPENAI_API_KEY="..."       # Judge model in training env
export LAUGHLOOP_ADAPTER_ID="..." # After first training run

# For deployed mode (Vercel + R2)
export R2_ACCOUNT_ID="..."
export R2_ACCESS_KEY_ID="..."
export R2_SECRET_ACCESS_KEY="..."
```

Or copy `.env.example` to `.env`.

## Prime CLI Commands

These require the `prime` CLI to be installed and authenticated:

- `prime login` - Authenticate
- `prime inference models` - List available models for inference
- `prime rl models` - List available models for RL training
- `prime rl run configs/rl.toml` - Start RL training
- `prime env install laughloop-reward --path ./environments` - Install the verifiers environment
- `prime deployments list` - Check adapter deployment status

## Architecture Notes

### Auto-Pipeline (in server.py)

After 20+ labeled interactions, the backend automatically:
1. Exports a training batch (inline, no CLI)
2. Starts an RL training run via Prime API
3. Monitors training progress (background task or lazy-poll)
4. Deploys the adapter when training completes
5. Hot-swaps the model (updates adapter ID in-memory)
6. Runs evals on 4 environments via Prime Hosted Evaluations API

### Serverless Mode (Vercel)

Vercel has no persistent processes, so the backend uses lazy-polling:
- State persisted to R2 (`pipeline/state.json`)
- Each GET request to `/pipeline` or `/evals` triggers one poll cycle
- Training/deployment/eval status updated incrementally per request

### Storage

- **Local dev**: JSONL files in `app/backend/logs/`, in-memory state
- **Deployed**: Cloudflare R2 via boto3 S3 client, state in R2

### Eval Environments

`primeintellect/aime2026`, `primeintellect/gsm8k`, `primeintellect/wordle`, `prime/tau2-synth`

## Common Gotchas

- The frontend `NEXT_PUBLIC_API_URL` is baked at build time. Changing it requires a redeploy.
- In local dev, the frontend proxies `/api/*` to `localhost:8000` via `next.config.ts` rewrites.
- R2 credentials are S3-compatible access key + secret (not regular Cloudflare API tokens).
- The backend CORS is fully open (`allow_origins=["*"]`).
- `vercel.json` sets `"trailingSlash": false` to avoid 308 redirects.
- Training pipeline state resets on backend restart in local dev (not persisted to disk).

## Code Style

- Python: standard formatting, type hints, pathlib for paths
- TypeScript: strict mode, interfaces in `api.ts`
- Frontend: Next.js App Router, Tailwind v4, monochrome design, no emojis in UI
- No pre-commit hooks configured
