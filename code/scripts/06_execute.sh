#!/bin/bash
#
# Script 6: Execute skills dynamically
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib.sh"

init_config

log_info "=========================================="
log_info "Step 6: Dynamic Execution"
log_info "=========================================="

QUEUE_FILE="$TASKS_DIR/run_queue.txt"

if [ ! -f "$QUEUE_FILE" ]; then
    log_error "Queue file not found: $QUEUE_FILE"
    log_error "Please run step 5 (generate execution queue) first"
    exit 1
fi

# Count tasks
task_count=$(wc -l < "$QUEUE_FILE")
log_info "Found $task_count execution tasks"
if [ "$task_count" -eq 0 ]; then
    log_warn "Execution queue is empty; nothing to run"
    exit 0
fi

STATE_FILE="${RUN_QUEUE_STATE_FILE:-$TASKS_DIR/run_queue_state.jsonl}"
RUN_QUEUE_LIMIT="${RUN_QUEUE_LIMIT:-0}"

# Check Docker image
DOCKER_IMAGE="${DOCKER_IMAGE:-claude-skill-sandbox}"
if ! docker image inspect "$DOCKER_IMAGE" &>/dev/null; then
    if [ "${SKIP_EXECUTION:-false}" = "true" ]; then
        log_warn "Docker image '$DOCKER_IMAGE' not found; SKIP_EXECUTION=true, skipping execution"
        exit 0
    fi
    log_error "Docker image '$DOCKER_IMAGE' not found"
    log_info "Build it first: python3 helper.py build --mode lite"
    exit 1
fi

# Run batch executor
python3 "$PROJECT_ROOT/executor/batch_runner.py" "$QUEUE_FILE" \
    --workers="${EXEC_WORKERS:-3}" \
    --limit="$RUN_QUEUE_LIMIT" \
    --state-file="$STATE_FILE" \
    --config="$PROJECT_ROOT/config.yaml"

log_success "Dynamic execution complete!"
log_info "Execution logs in: $EXECUTION_LOGS_DIR/"
log_info "Execution state: $STATE_FILE"
log_info "Timeouts with NOVA reports are recorded as captured artifacts."
log_info "Uncaptured failures fail this step unless ALLOW_EXECUTION_FAILURES=true."
