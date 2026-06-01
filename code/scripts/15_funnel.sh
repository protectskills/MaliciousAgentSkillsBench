#!/bin/bash
#
# Script 15: Dataset funnel summary (paper Table "Data sources and analysis funnel")
#
# Re-derives the per-source funnel (Repos / Snapshot / Candidates / Confirmed)
# from the released data/skills_dataset.csv. Operates on the released snapshot
# CSV and needs no crawl, download, or sandbox run.
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib.sh"

ANALYSIS_DIR="$PROJECT_ROOT/analysis"

log_info "=========================================="
log_info "Step 15: Dataset Funnel Summary"
log_info "=========================================="

cd "$ANALYSIS_DIR"
python3 dataset_funnel.py "$@"

log_success "Dataset funnel summary complete!"
