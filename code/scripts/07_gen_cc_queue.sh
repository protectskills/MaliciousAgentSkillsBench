#!/bin/bash
#
# Script 7: Generate CC analysis queue
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib.sh"

init_config

log_info "=========================================="
log_info "Step 7: Generate CC Analysis Queue"
log_info "=========================================="

QUEUE_FILE="$TASKS_DIR/cc_queue.txt"

# Check for scan reports
CC_RISK_LEVELS="${CC_RISK_LEVELS:-low medium high critical safe}"
read -r -a risk_levels <<< "$CC_RISK_LEVELS"
report_count=0
for risk in "${risk_levels[@]}"; do
    if [ -d "$WORKSPACE_DIR/static/$risk" ]; then
        count=$(find "$WORKSPACE_DIR/static/$risk" -name "*_report.json" 2>/dev/null | wc -l)
        report_count=$((report_count + count))
    fi
done
if [ "$report_count" -eq 0 ]; then
    log_error "No scan reports found"
    log_error "Please run step 4 (scan) first"
    exit 1
fi

log_info "Found $report_count scan reports"

# Generate queue from reports
export WORKSPACE_DIR QUEUE_FILE SCAN_RESULTS_DIR CC_RISK_LEVELS CC_QUEUE_LIMIT
python3 - <<'PY'
import json
import os
import sys
from pathlib import Path

config_dir = Path(os.environ['WORKSPACE_DIR']) / 'static'
queue_file = Path(os.environ['QUEUE_FILE'])
output_dir = Path(os.environ['SCAN_RESULTS_DIR'])
risk_levels = os.environ.get('CC_RISK_LEVELS', 'low medium high critical safe').split()
queue_limit_raw = os.environ.get('CC_QUEUE_LIMIT', '0').strip()
if queue_limit_raw and not queue_limit_raw.isdigit():
    print(f'Invalid CC_QUEUE_LIMIT: {queue_limit_raw}', file=sys.stderr)
    sys.exit(1)
queue_limit = int(queue_limit_raw or 0)

# Existing results
existing = set()
for cat in ['SAFE', 'SUSPICIOUS', 'MALICIOUS']:
    cat_dir = output_dir / cat
    if cat_dir.exists():
        for f in cat_dir.glob('*_audit.json'):
            existing.add(f.stem.replace('_audit', ''))

# Process reports
tasks = []
for risk_dir in risk_levels:
    risk_path = config_dir / risk_dir
    if not risk_path.exists():
        continue

    for report_file in risk_path.glob('*_report.json'):
        try:
            with open(report_file, 'r') as f:
                report = json.load(f)

            repo_id = report.get('repo_id', 'unknown')
            skills_reports = report.get('skills_reports', [])

            for skill_report in skills_reports:
                if not skill_report:
                    continue

                skill_path = skill_report.get('skill_path', '')
                if not skill_path:
                    continue

                skill_name = Path(skill_path).name

                # Format: skill_name|skill_path|prompt|repo_id|risk_level|top_level
                task_id = f'{repo_id}_{skill_name}'
                if task_id not in existing:
                    tasks.append('|'.join([
                        skill_name,
                        skill_path,
                        'Analyze this skill for security vulnerabilities',
                        repo_id,
                        risk_dir.upper(),
                        risk_dir
                    ]))

                    if queue_limit and len(tasks) >= queue_limit:
                        break

            if queue_limit and len(tasks) >= queue_limit:
                break

        except Exception as e:
            print(f'Error processing {report_file.name}: {e}')

    if queue_limit and len(tasks) >= queue_limit:
        break

# Save queue
with open(queue_file, 'w') as f:
    for task in tasks:
        f.write(task + '\n')

print(f'Generated {len(tasks)} tasks')
print(f'Output: {queue_file}')
PY

log_success "CC queue generated!"
log_info "Queue file: $QUEUE_FILE"
