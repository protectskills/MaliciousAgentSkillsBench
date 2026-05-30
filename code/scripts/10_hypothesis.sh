#!/bin/bash
#
# Script 10: Hypothesis testing (paper RQ2 / Section 5.4 + Appendix)
#
# Runs the pairwise association tests (Fisher's exact with Bonferroni
# correction) and the severity Mann-Whitney U test on the released
# data/malicious_skills.csv. Like step 9, this operates on the released
# labeled set and does not require a crawl/download/sandbox run.
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib.sh"

ANALYSIS_DIR="$PROJECT_ROOT/analysis"
OUTDIR="${ANALYSIS_OUTDIR:-$PROJECT_ROOT/analysis_output/hypothesis}"

log_info "=========================================="
log_info "Step 10: Hypothesis Testing"
log_info "=========================================="

cd "$ANALYSIS_DIR"
python3 hypothesis_tests.py --outdir "$OUTDIR" "$@"

log_success "Hypothesis testing complete!"
log_info "Outputs in: $OUTDIR"
