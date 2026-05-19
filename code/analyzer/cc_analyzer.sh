#!/bin/bash
#
# CC (Claude Code) Security Analyzer v1.0
# Performs optional LLM-assisted triage using the local Claude Code CLI.
#

set -e

# Configuration
OUTPUT_SUFFIX="_audit.json"
JOBS=${CC_JOBS:-10}
MAX_RETRIES=${CC_MAX_RETRIES:-3}
CC_MODEL=${CC_MODEL:-claude-sonnet-4-6}

# Colors for output
export GREEN='\033[0;32m'
export BLUE='\033[0;34m'
export RED='\033[0;31m'
export YELLOW='\033[1;33m'
export CYAN='\033[0;36m'
export NC='\033[0m'

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Source config loader
source "$PROJECT_ROOT/scripts/lib.sh"

# Initialize paths using config
init_config

# Output directories
OUTPUT_DIR="$SCAN_RESULTS_DIR"
mkdir -p "$OUTPUT_DIR"/{SAFE,SUSPICIOUS,MALICIOUS,ERROR,logs}

# Log file
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="$OUTPUT_DIR/logs/cc_analyze_${TIMESTAMP}.log"

# Cache files
INDEX_FILE="$OUTPUT_DIR/index.cache"
TODO_FILE="$OUTPUT_DIR/todo.cache"
SKIPPED_LOG="$OUTPUT_DIR/logs/skipped.log"

# API Key configuration.
# LEGACY: api_keys.conf is the older multi-key rotation path retained for
# backward compatibility. The recommended setup uses the local Claude Code
# login (see helper.py init); leave api_keys.conf absent for that flow.
API_KEY_CONF="$PROJECT_ROOT/api_keys.conf"
KEY_INDEX_FILE="/tmp/cc_api_key_index.txt"
LOCK_FILE="/tmp/cc_api_key_index.lock"

# Initialize API key index
mkdir -p "$(dirname "$KEY_INDEX_FILE")" 2>/dev/null
echo "0" > "$KEY_INDEX_FILE"

# Command line arguments
QUEUE_FILE="${1:-}"
SKIP_CROSS_CHECK="${2:-false}"

log() {
    local msg="$1"
    echo -e "$msg"
    echo -e "$msg" | sed 's/\x1b\[[0-9;]*m//g' >> "$LOG_FILE"
}

# Get next API key from pool
get_next_api_key() {
    if [ ! -f "$API_KEY_CONF" ]; then
        return 1
    fi

    (
        flock -x 200
        local index=$(cat "$KEY_INDEX_FILE" 2>/dev/null || echo "0")
        local keys=($(grep -v '^#' "$API_KEY_CONF" 2>/dev/null | grep -v '^[[:space:]]*$'))
        if [ ${#keys[@]} -eq 0 ]; then
            return 1
        fi
        local key="${keys[$index]}"
        local next_index=$(( (index + 1) % ${#keys[@]} ))
        echo "$next_index" > "$KEY_INDEX_FILE"
        echo "$key"
    ) 200>"$LOCK_FILE"
}

# Core analysis function
analyze_single_skill() {
    local skill_dir="$1"
    local repo_id="$2"
    local skill_name="$3"
    local risk_level="${4:-unknown}"

    local filename="${repo_id}_${skill_name}${OUTPUT_SUFFIX}"
    local tmp_out=$(mktemp)

    # Load prompt
    local prompt_file="$PROJECT_ROOT/analyzer/prompts/audit_prompt.txt"
    if [ ! -f "$prompt_file" ]; then
        log "${RED}Error: Prompt file not found: $prompt_file${NC}"
        echo "ERROR|$repo_id|$skill_name|PROMPT_NOT_FOUND"
        return
    fi

    local custom_prompt=$(cat "$prompt_file")

    # Get API key
    local current_api_key=""
    if current_api_key=$(get_next_api_key 2>/dev/null); then
        export ANTHROPIC_AUTH_TOKEN="$current_api_key"
    fi

    # Execute Claude Code triage
    set +e
    claude -p \
        --model "$CC_MODEL" \
        --output-format json \
        --append-system-prompt "$custom_prompt" \
        "Analyze Skill Directory: ${skill_dir}" > "$tmp_out" 2>&1 < /dev/null

    local exit_code=$?
    set -e

    if [ ! -s "$tmp_out" ]; then
        exit_code=1
    fi

    # Process result
    if [ $exit_code -eq 0 ]; then
        local raw=$(cat "$tmp_out")

        # Clean JSON response
        local clean_json=$(python3 -c "
import sys, json, re
try:
    raw_input = sys.stdin.read()
    start_index = raw_input.find('{')
    if start_index == -1:
        print(raw_input)
        sys.exit(0)
    json_text = raw_input[start_index:]

    # Parse wrapper
    try:
        wrapper = json.loads(json_text)
        if isinstance(wrapper, dict) and 'result' in wrapper:
            inner_content = wrapper['result']
        else:
            inner_content = json_text
    except:
        match = re.search(r'(\{.*\})', json_text, re.DOTALL)
        if match:
            inner_content = match.group(1)
        else:
            inner_content = json_text

    # Extract JSON from markdown
    match = re.search(r'\`\`\`(?:json)?\s*(\{.*?\})\s*\`\`\`', inner_content, re.DOTALL | re.IGNORECASE)
    if match:
        final_json = match.group(1)
    else:
        # Greedy match
        s = inner_content.find('{')
        e = inner_content.rfind('}')
        if s != -1 and e != -1:
            final_json = inner_content[s:e+1]
        else:
            final_json = inner_content

    json.loads(final_json)
    print(final_json)
except:
    print(raw_input)
" <<< "$raw")

        # Validate and save
        if echo "$clean_json" | jq . >/dev/null 2>&1; then
            clean_json=$(SKILL_PATH="$skill_dir" REPO_ID="$repo_id" SKILL_NAME="$skill_name" RISK_LEVEL="$risk_level" python3 -c "
import json, os, sys

data = json.load(sys.stdin)
data.setdefault('metadata', {})
data['metadata'].update({
    'skill_path': os.environ['SKILL_PATH'],
    'repo_id': os.environ['REPO_ID'],
    'skill_name': os.environ['SKILL_NAME'],
    'risk_level': os.environ['RISK_LEVEL'],
})
data.setdefault('skill_path', os.environ['SKILL_PATH'])
print(json.dumps(data, indent=2))
" <<< "$clean_json")
            local status=$(echo "$clean_json" | jq -r '.audit_summary.intent_alignment_status' | tr -d '[:space:]')

            if [ -z "$status" ] || [ "$status" == "null" ]; then
                echo "$clean_json" > "${OUTPUT_DIR}/ERROR/${filename}.status_missing.err"
                echo "ERROR|$repo_id|$skill_name|STATUS_MISSING"
            else
                local target_dir="$OUTPUT_DIR/ERROR"
                case "$status" in
                    "SAFE") target_dir="$OUTPUT_DIR/SAFE" ;;
                    "SUSPICIOUS") target_dir="$OUTPUT_DIR/SUSPICIOUS" ;;
                    "MALICIOUS") target_dir="$OUTPUT_DIR/MALICIOUS" ;;
                    *) target_dir="$OUTPUT_DIR/ERROR" ;;
                esac
                echo "$clean_json" > "${target_dir}/${filename}"
                echo "DONE|$repo_id|$skill_name|$status"
            fi
        else
            echo "$raw" > "${OUTPUT_DIR}/ERROR/${filename}.parse_err"
            echo "ERROR|$repo_id|$skill_name|INVALID_JSON"
        fi
    else
        echo "ERROR|$repo_id|$skill_name|API_FAIL"
    fi

    rm -f "$tmp_out"
}

export -f analyze_single_skill get_next_api_key
export OUTPUT_DIR OUTPUT_SUFFIX PROJECT_ROOT API_KEY_CONF KEY_INDEX_FILE LOCK_FILE CC_MODEL

# Main execution
main() {
    log "${BLUE}======================================${NC}"
    log "${BLUE}CC Security Analyzer v1.0${NC}"
    log "${BLUE}======================================${NC}"

    # Check queue file
    if [ -z "$QUEUE_FILE" ] || [ ! -f "$QUEUE_FILE" ]; then
        log "${RED}Error: Queue file not specified or not found${NC}"
        log "Usage: $0 <queue_file> [skip_cross_check]"
        exit 1
    fi

    TOTAL_COUNT=$(wc -l < "$QUEUE_FILE")
    log "Queue file: $QUEUE_FILE"
    log "Total tasks: ${GREEN}${TOTAL_COUNT}${NC}"
    log "Workers: $JOBS"

    # Generate TODO list (skip existing)
    log "${YELLOW}Generating TODO list...${NC}"

    python3 -c "
import os, sys

queue_file = '$QUEUE_FILE'
scan_dir = '$OUTPUT_DIR'
output_suffix = '$OUTPUT_SUFFIX'
skip_cross_check = '$SKIP_CROSS_CHECK'

# Load existing results
existing_files = set()
for subdir in ['SAFE', 'SUSPICIOUS', 'MALICIOUS', 'ERROR']:
    path = os.path.join(scan_dir, subdir)
    if os.path.exists(path):
        existing_files.update(os.listdir(path))

print(f'Existing results: {len(existing_files)}')

# Process queue
todo_count = 0
with open(queue_file, 'r') as f_in, open('$TODO_FILE', 'w') as f_out:
    for line in f_in:
        line = line.strip()
        if not line:
            continue

        parts = line.split('|')
        if len(parts) < 4:
            continue

        skill_name = parts[0]
        repo_id = parts[3]
        target_name = f'{repo_id}_{skill_name}{output_suffix}'

        # Skip if already exists
        if target_name in existing_files:
            continue

        f_out.write(line + '\\n')
        todo_count += 1

print(f'TODO count: {todo_count}')
"

    TOTAL_TODO=$(wc -l < "$TODO_FILE")

    if [ "$TOTAL_TODO" -eq 0 ]; then
        log "${GREEN}All tasks already completed!${NC}"
        exit 0
    fi

    log "Tasks to process: ${GREEN}${TOTAL_TODO}${NC}"
    log "----------------------------------------"

    # Process queue
    COUNT_SAFE=0
    COUNT_SUSP=0
    COUNT_MAL=0
    COUNT_ERR=0
    PROCESSED=0

    while read -r line; do
        PROCESSED=$((PROCESSED + 1))
        IFS='|' read -r status repo skill verdict <<< "$line"

        if [ "$status" == "DONE" ]; then
            case "$verdict" in
                "SAFE") ((++COUNT_SAFE)); log "[$PROCESSED/$TOTAL_TODO] ${BLUE}${repo}_${skill}${NC} -> ${GREEN}[SAFE]${NC}" ;;
                "SUSPICIOUS") ((++COUNT_SUSP)); log "[$PROCESSED/$TOTAL_TODO] ${BLUE}${repo}_${skill}${NC} -> ${YELLOW}[SUSPICIOUS]${NC}" ;;
                "MALICIOUS") ((++COUNT_MAL)); log "[$PROCESSED/$TOTAL_TODO] ${BLUE}${repo}_${skill}${NC} -> ${RED}[MALICIOUS]${NC}" ;;
                *) ((++COUNT_ERR)); log "[$PROCESSED/$TOTAL_TODO] ${repo}_${skill} -> ${CYAN}[${verdict}]${NC}" ;;
            esac
        else
            ((++COUNT_ERR))
            log "[$PROCESSED/$TOTAL_TODO] ${RED}Failed: ${repo}_${skill}${NC}"
        fi

        if (( PROCESSED % 20 == 0 )); then
            log "${CYAN}Progress: SAFE=$COUNT_SAFE | SUSP=$COUNT_SUSP | MAL=$COUNT_MAL | ERR=$COUNT_ERR${NC}"
        fi
    done < <(
        while IFS= read -r queue_line; do
            printf '%s\0' "$queue_line"
        done < "$TODO_FILE" | xargs -0 -P "$JOBS" -n 1 bash -c '
        IFS="|" read -r skill_name skill_path prompt repo_id risk_level rest <<< "$1"
        analyze_single_skill "$skill_path" "$repo_id" "$skill_name" "$risk_level"
    ' _
    )

    log "======================================"
    log "Analysis Complete!"
    log "SAFE: $COUNT_SAFE | SUSPICIOUS: $COUNT_SUSP | MALICIOUS: $COUNT_MAL | ERR: $COUNT_ERR"
    log "======================================"
}

main "$@"
