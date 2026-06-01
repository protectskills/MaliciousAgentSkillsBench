#!/bin/bash
#
# Script 13: Attacker-archetype statistics (RQ2)
#
# Re-derives the corresponding paper artifact from the released
# data/malicious_skills.csv. Like steps 9-10, this operates on the released
# labeled set and needs no crawl, download, or sandbox run.
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib.sh"

ANALYSIS_DIR="$PROJECT_ROOT/analysis"
OUTDIR="${ANALYSIS_OUTDIR:-$PROJECT_ROOT/analysis_output/archetypes}"

log_info "=========================================="
log_info "Step 13: Attacker-archetype statistics (RQ2)"
log_info "=========================================="

cd "$ANALYSIS_DIR"
python3 archetypes.py --outdir "$OUTDIR" "$@"

log_success "Attacker-archetype statistics (RQ2) complete!"
log_info "Outputs in: $OUTDIR"
