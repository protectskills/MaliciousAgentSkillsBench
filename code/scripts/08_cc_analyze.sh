#!/bin/bash
#
# Script 8: Run CC analysis
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib.sh"

init_config

log_info "=========================================="
log_info "Step 8: CC Security Analysis"
log_info "=========================================="

QUEUE_FILE="$TASKS_DIR/cc_queue.txt"

if [ ! -f "$QUEUE_FILE" ]; then
    log_error "Queue file not found: $QUEUE_FILE"
    log_error "Please run step 7 (generate CC queue) first"
    exit 1
fi

# Make analyzer executable
chmod +x "$PROJECT_ROOT/analyzer/cc_analyzer.sh"

# Run analyzer
"$PROJECT_ROOT/analyzer/cc_analyzer.sh" "$QUEUE_FILE"

log_success "CC analysis complete!"
log_info "Results in: $SCAN_RESULTS_DIR/{SAFE,SUSPICIOUS,MALICIOUS}/"
