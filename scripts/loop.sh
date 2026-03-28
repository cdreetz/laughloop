#!/usr/bin/env bash
# ============================================================================
# LaughLoop — Continual Learning Loop
# ============================================================================
#
# This script runs one complete cycle of the feedback loop:
#   1. Export new training data from the log database
#   2. Install the verifiers environment
#   3. Run RL training via Prime hosted training
#   4. Deploy the new adapter
#
# Run manually:   bash scripts/loop.sh
# Run on cron:    */30 * * * * cd /path/to/laughloop && bash scripts/loop.sh >> logs/loop.log 2>&1
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Config
MIN_BATCH_SIZE="${LAUGHLOOP_MIN_BATCH:-20}"   # Minimum interactions before training
LOOP_LOG_DIR="${PROJECT_DIR}/logs"

# Setup
mkdir -p "$LOOP_LOG_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="${LOOP_LOG_DIR}/loop_${TIMESTAMP}.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

log "=========================================="
log "LaughLoop Training Loop — Starting"
log "=========================================="
log "Project: ${PROJECT_DIR}"
log "Min batch size: ${MIN_BATCH_SIZE}"

# ─────────────────────────────────────────────
# Step 1: Export training data
# ─────────────────────────────────────────────
log ""
log "Step 1: Exporting training data..."

EXPORT_OUTPUT=$(python "${PROJECT_DIR}/pipeline/export_batch.py" \
    --log "${PROJECT_DIR}/app/backend/logs/interactions.jsonl" \
    --min-batch-size "$MIN_BATCH_SIZE" 2>&1) || true

echo "$EXPORT_OUTPUT" >> "$LOG_FILE"

if echo "$EXPORT_OUTPUT" | grep -q "No batch exported\|Skipping export"; then
    log "Not enough new data for training. Waiting for more feedback."
    log "Loop complete (no training needed)."
    exit 0
fi

BATCH_FILE=$(echo "$EXPORT_OUTPUT" | grep "Batch ready for training:" | awk '{print $NF}')
log "Exported batch: ${BATCH_FILE}"

# ─────────────────────────────────────────────
# Step 2: Install the environment
# ─────────────────────────────────────────────
log ""
log "Step 2: Installing laughloop-reward environment..."

prime env install laughloop-reward --path "${PROJECT_DIR}/environments" 2>&1 | tee -a "$LOG_FILE"

# ─────────────────────────────────────────────
# Step 3: Run RL training
# ─────────────────────────────────────────────
log ""
log "Step 3: Starting RL training..."

# Update the data path in the config to point to the new batch
export LAUGHLOOP_DATA_DIR="${PROJECT_DIR}/data/batches"

prime rl run "${PROJECT_DIR}/configs/rl.toml" 2>&1 | tee -a "$LOG_FILE"

log "Training complete."

# ─────────────────────────────────────────────
# Step 4: Deploy the new adapter
# ─────────────────────────────────────────────
log ""
log "Step 4: Deploying new adapter..."

python "${PROJECT_DIR}/scripts/deploy_adapter.py" 2>&1 | tee -a "$LOG_FILE"

# ─────────────────────────────────────────────
# Done
# ─────────────────────────────────────────────
log ""
log "=========================================="
log "LaughLoop Training Loop — Complete"
log "=========================================="
log "The model should now be funnier!"
log "Next loop will run when enough new feedback is collected."
