#!/bin/bash
#
# Script 5: Generate execution queue from scanned skills
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib.sh"

init_config

log_info "=========================================="
log_info "Step 5: Generate Execution Queue"
log_info "=========================================="

QUEUE_FILE="$TASKS_DIR/run_queue.txt"
mkdir -p "$(dirname "$QUEUE_FILE")"
: > "$QUEUE_FILE"

RUN_QUEUE_SOURCE="${RUN_QUEUE_SOURCE:-static}"
RUN_FROM_CATEGORIES="${RUN_FROM_CATEGORIES:-SUSPICIOUS MALICIOUS SAFE}"
RUN_FROM_RISKS="${RUN_FROM_RISKS:-critical high medium low safe}"
if [ -z "${RUN_PROMPT_TEMPLATE:-}" ]; then
    RUN_PROMPT_TEMPLATE="Use the {skill_name} skill to design and run a sandboxed test for this skill. Create any temporary files or helper scripts needed inside the current working directory, exercise the skill as realistically as possible, and summarize what was tested and what happened. Do not ask follow-up questions unless execution is impossible."
fi
export RUN_PROMPT_TEMPLATE

if [ "$RUN_QUEUE_SOURCE" = "cc" ]; then
    if [ ! -d "$SCAN_RESULTS_DIR" ]; then
        log_error "Scan results directory not found: $SCAN_RESULTS_DIR"
        log_error "Please run optional CC analysis first or use RUN_QUEUE_SOURCE=static"
        exit 1
    fi

    read -r -a source_categories <<< "$RUN_FROM_CATEGORIES"

    # Count executable analysis results
    result_count=0
    for category in "${source_categories[@]}"; do
        category_dir="$SCAN_RESULTS_DIR/$category"
        if [ -d "$category_dir" ]; then
            count=$(ls -1 "$category_dir"/*_audit.json 2>/dev/null | wc -l)
            result_count=$((result_count + count))
        fi
    done
    if [ "$result_count" -eq 0 ]; then
        log_warn "No analysis results found in: $RUN_FROM_CATEGORIES"
        exit 0
    fi

    log_info "Found $result_count analysis results in: $RUN_FROM_CATEGORIES"

    # Generate execution queue from CC results
    export QUEUE_FILE SCAN_RESULTS_DIR RUN_FROM_CATEGORIES RUN_PROMPT_TEMPLATE
    python3 - <<'PY'
import json
import os
import sys
from pathlib import Path

queue_file = Path(os.environ['QUEUE_FILE'])
scan_results_dir = Path(os.environ['SCAN_RESULTS_DIR'])
categories = os.environ.get('RUN_FROM_CATEGORIES', 'SUSPICIOUS MALICIOUS SAFE').split()
prompt_template = os.environ['RUN_PROMPT_TEMPLATE']

tasks = []

for category in categories:
    category_dir = scan_results_dir / category
    if not category_dir.exists():
        continue

    for audit_file in category_dir.glob('*_audit.json'):
        try:
            with open(audit_file, 'r') as f:
                audit = json.load(f)

            # Parse filename: rest_1_skillname_audit.json
            filename = audit_file.name
            if filename.endswith('_audit.json'):
                filename = filename[:-len('_audit.json')]
            else:
                filename = audit_file.stem
            parts = filename.split('_')

            if len(parts) >= 3:
                repo_id = f'{parts[0]}_{parts[1]}'
                skill_name = '_'.join(parts[2:])

                # Get skill path from audit
                skill_path = audit.get('skill_path', '')
                if not skill_path:
                    continue

                # Format: skill_name|skill_path|prompt|repo_id|risk_level|top_level
                skill_name = skill_name.replace('|', '/')
                prompt = prompt_template.replace('{skill_name}', skill_name)
                if '|' in prompt:
                    prompt = prompt.replace('|', '/')
                tasks.append('|'.join([
                    skill_name,
                    skill_path,
                    prompt,
                    repo_id,
                    category,
                    category.lower()
                ]))

        except Exception as e:
            print(f'Error processing {audit_file.name}: {e}')

# Save queue
with open(queue_file, 'w') as f:
    for task in tasks:
        f.write(task + '\n')

print(f'Generated {len(tasks)} execution tasks')
print(f'Output: {queue_file}')
PY
else
    read -r -a source_risks <<< "$RUN_FROM_RISKS"

    # Count static scan reports
    report_count=0
    for risk in "${source_risks[@]}"; do
        risk_dir="$WORKSPACE_DIR/static/$risk"
        if [ -d "$risk_dir" ]; then
            count=$(find "$risk_dir" -name "*_report.json" 2>/dev/null | wc -l)
            report_count=$((report_count + count))
        fi
    done
    if [ "$report_count" -eq 0 ]; then
        log_warn "No static scan reports found in: $RUN_FROM_RISKS"
        exit 0
    fi

    log_info "Found $report_count static scan reports in: $RUN_FROM_RISKS"

    # Generate execution queue from static scan reports
    export QUEUE_FILE WORKSPACE_DIR RUN_FROM_RISKS RUN_PROMPT_TEMPLATE
    python3 - <<'PY'
import json
import os
from pathlib import Path

queue_file = Path(os.environ['QUEUE_FILE'])
workspace_dir = Path(os.environ['WORKSPACE_DIR']) / 'static'
risks = os.environ.get('RUN_FROM_RISKS', 'critical high medium low safe').split()
prompt_template = os.environ['RUN_PROMPT_TEMPLATE']

tasks = []
candidate_count = 0

for risk in risks:
    risk_dir = workspace_dir / risk
    if not risk_dir.exists():
        continue

    for report_file in sorted(risk_dir.glob('*_report.json')):
        try:
            with open(report_file, 'r') as f:
                report = json.load(f)

            repo_id = str(report.get('repo_id', report_file.stem.replace('_report', '')))
            skills_reports = report.get('skills_reports', [])
            candidate_count += sum(1 for skill_report in skills_reports if skill_report and skill_report.get('skill_path', ''))

            for skill_report in skills_reports:
                if not skill_report:
                    continue

                skill_path = skill_report.get('skill_path', '')
                if not skill_path:
                    continue

                skill_name = Path(skill_path).name.replace('|', '/')
                prompt = prompt_template.replace('{skill_name}', skill_name).replace('|', '/')
                tasks.append('|'.join([
                    skill_name,
                    skill_path,
                    prompt,
                    repo_id,
                    risk.upper(),
                    risk
                ]))

        except Exception as e:
            print(f'Error processing {report_file.name}: {e}')

with open(queue_file, 'w') as f:
    for task in tasks:
        f.write(task + '\n')

print(f'Candidate skills: {candidate_count}')
print(f'Generated {len(tasks)} execution tasks')
print(f'Output: {queue_file}')
PY
fi

log_success "Execution queue generated!"
log_info "Queue file: $QUEUE_FILE"
