#!/bin/bash
#
# Script 9: Co-occurrence matrix generation (paper RQ2 / Section 5.4)
#
# Re-derives the pattern co-occurrence matrix, conditional-probability matrix,
# odds-ratio matrix, phi matrix, and the co-occurrence heatmap from the
# released data/malicious_skills.csv. Unlike steps 01-08 (the registry-to-
# confirmed funnel), this step operates on the released labeled set, so it does
# not require a crawl, download, or sandbox run.
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib.sh"

ANALYSIS_DIR="$PROJECT_ROOT/analysis"
OUTDIR="${ANALYSIS_OUTDIR:-$PROJECT_ROOT/analysis_output/cooccurrence}"

log_info "=========================================="
log_info "Step 9: Co-occurrence Matrix Generation"
log_info "=========================================="

cd "$ANALYSIS_DIR"
python3 cooccurrence.py --outdir "$OUTDIR" "$@"

log_success "Co-occurrence analysis complete!"
log_info "Outputs in: $OUTDIR"
