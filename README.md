# LaughLoop 🔁😂

**Continual Learning Chat App — An AI that gets funnier over time.**

LaughLoop is an end-to-end MVP demonstrating online reinforcement learning. It's a chat app where every AI response tries to be funny. Users click "😂 Haha" on responses they find funny, and that signal feeds back into RL training — making the model progressively funnier.

## Architecture

```
┌─────────────┐    ┌──────────────┐    ┌────────────────┐
│  React Chat │───▶│  FastAPI     │───▶│  SQLite Log DB │
│  Frontend   │◀───│  Backend     │    │  (interactions │
│  + Haha btn │    │  /chat       │    │   + feedback)  │
└─────────────┘    │  /feedback   │    └───────┬────────┘
                   └──────────────┘            │
                                               ▼
                   ┌──────────────┐    ┌────────────────┐
                   │  prime rl    │◀───│  Pipeline:     │
                   │  run         │    │  Export → JSONL │
                   │  rl.toml     │    │  batch data    │
                   └──────┬───────┘    └────────────────┘
                          │
                          ▼
                   ┌──────────────┐    ┌────────────────┐
                   │  Verifiers   │    │  Model Swap:   │
                   │  Environment │    │  Update        │
                   │  (reward =   │───▶│  endpoint to   │
                   │   haha rate) │    │  new adapter   │
                   └──────────────┘    └────────────────┘
                                               │
                                               ▼
                                        ┌──────────────┐
                                        │  Loop back   │
                                        │  to serving  │
                                        └──────────────┘
```

## Components

| Component | Location | Purpose |
|-----------|----------|---------|
| Chat Frontend | `app/frontend/` | React chat UI with Haha feedback buttons |
| Chat Backend | `app/backend/` | FastAPI: serves chat, collects feedback, logs everything |
| Log Database | `app/backend/laughloop.db` | SQLite storing all interactions + feedback |
| Data Pipeline | `pipeline/` | Exports logged data → training-ready JSONL batches |
| RL Environment | `environments/laughloop_reward/` | Verifiers environment that loads batches for RL training |
| Training Config | `configs/rl.toml` | Config for `prime rl run` |
| Orchestrator | `scripts/loop.sh` | Cron-able script: export → train → deploy → repeat |

## Quick Start

### 1. Prerequisites
```bash
uv tool install prime
prime login
pip install verifiers
```

### 2. Set up the app
```bash
cd app/backend
pip install -r requirements.txt
python server.py  # starts on :8000
```

### 3. Open the frontend
```bash
cd app/frontend
# Open index.html in browser, or serve with:
python -m http.server 3000
```

### 4. Collect some data
Chat with the app. Click 😂 on funny responses. Build up ~100+ interactions.

### 5. Run the training loop
```bash
# Export data for training
python pipeline/export_batch.py

# Install the environment
prime env install laughloop-reward --path ./environments

# Run RL training
prime rl run configs/rl.toml

# Deploy the new adapter
python scripts/deploy_adapter.py
```

### 6. Automate the loop
```bash
# Run the full loop on a schedule
bash scripts/loop.sh
```

## How It Works

1. **Serve**: Model generates funny responses to user messages
2. **Collect**: Every interaction is logged with the user's 😂 feedback
3. **Export**: Pipeline converts logs into training-ready JSONL batches
4. **Train**: Verifiers environment loads the batch; RL training uses haha-rate as reward
5. **Deploy**: New adapter is deployed; model serves with updated weights
6. **Repeat**: The loop runs continuously, making the model funnier over time
