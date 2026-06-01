#!/bin/bash
#
# Script 11: RQ1 threat-landscape statistics
#
# Re-derives the corresponding paper artifact from the released
# data/malicious_skills.csv. Like steps 9-10, this operates on the released
# labeled set and needs no crawl, download, or sandbox run.
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib.sh"

ANALYSIS_DIR="$PROJECT_ROOT/analysis"
OUTDIR="${ANALYSIS_OUTDIR:-$PROJECT_ROOT/analysis_output/rq1}"

log_info "=========================================="
log_info "Step 11: RQ1 threat-landscape statistics"
log_info "=========================================="

cd "$ANALYSIS_DIR"
python3 rq1_landscape.py --outdir "$OUTDIR" "$@"

log_success "RQ1 threat-landscape statistics complete!"
log_info "Outputs in: $OUTDIR"
