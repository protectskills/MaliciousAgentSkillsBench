#!/bin/bash
#
# Dynamic Skill Executor using a host Claude Code login.
# Runs one skill in the Docker sandbox and records tcpdump, strace,
# filesystem diffs, Claude output, and NOVA hook reports.
#

set -euo pipefail

SKILL_NAME="${1:-unknown}"
SKILL_PATH="${2:-}"
USER_PROMPT="${3:-Read the skill and execute it}"
REPO_ID="${4:-unknown}"
RISK_LEVEL="${5:-unknown}"
IN_PLACE_LOG="${6:-false}"

USE_NOVA="${USE_NOVA:-true}"
NOVA_BLOCK="${NOVA_BLOCK:-false}"
NOVA_PROVIDER="${NOVA_PROVIDER:-tracer}"
NOVA_PROFILE="${NOVA_PROFILE:-record}"
TIMEOUT="${EXEC_TIMEOUT:-900}"
DOCKER_IMAGE="${DOCKER_IMAGE:-claude-skill-sandbox}"
DOCKER_CMD="${DOCKER_CMD:-docker}"
AGENT_CLI="${AGENT_CLI:-claude}"
AUTH_MODE="${AUTH_MODE:-host_claude}"
RUN_ID="${RUN_ID:-$(date +%Y%m%d_%H%M%S)_$$}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$(dirname "$SCRIPT_DIR")}"
EXECUTION_LOGS_DIR="${EXECUTION_LOGS_DIR:-$PROJECT_ROOT/workspace/dynamic}"
CLAUDE_CREDENTIALS_FILE="${CLAUDE_CREDENTIALS_FILE:-$HOME/.claude/.credentials.json}"

safe_component() {
    printf '%s' "$1" | tr -c 'A-Za-z0-9_.-' '_' | sed 's/^[._]*//; s/[._]*$//' | cut -c1-180
}

if ! [[ "$TIMEOUT" =~ ^[0-9]+$ ]] || [ "$TIMEOUT" -le 0 ]; then
    echo "Error: EXEC_TIMEOUT must be a positive integer number of seconds: $TIMEOUT"
    exit 1
fi

SAFE_SKILL_NAME="$(safe_component "$SKILL_NAME")"
SAFE_REPO_ID="$(safe_component "$REPO_ID")"
SAFE_RISK_LEVEL="$(safe_component "$RISK_LEVEL")"
SAFE_RUN_ID="$(safe_component "$RUN_ID")"
SAFE_SKILL_NAME="${SAFE_SKILL_NAME:-unknown}"
SAFE_REPO_ID="${SAFE_REPO_ID:-unknown}"
SAFE_RISK_LEVEL="${SAFE_RISK_LEVEL:-unknown}"
SAFE_RUN_ID="${SAFE_RUN_ID:-run}"

if [ "$AGENT_CLI" != "claude" ]; then
    echo "Error: unsupported AGENT_CLI='$AGENT_CLI' (currently only 'claude' is implemented)"
    exit 1
fi

if [ "$AUTH_MODE" != "host_claude" ]; then
    echo "Error: unsupported AUTH_MODE='$AUTH_MODE' (currently only 'host_claude' is implemented)"
    exit 1
fi

if [ -z "$SKILL_PATH" ] || [ ! -d "$SKILL_PATH" ]; then
    echo "Error: skill path must be an existing directory: $SKILL_PATH"
    exit 1
fi

if [ ! -f "$CLAUDE_CREDENTIALS_FILE" ]; then
    echo "Error: Claude credentials file not found: $CLAUDE_CREDENTIALS_FILE"
    exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
    echo "Error: docker is not installed or not on PATH"
    exit 1
fi

read -r -a DOCKER_CMD_ARRAY <<< "$DOCKER_CMD"
if ! command -v "${DOCKER_CMD_ARRAY[0]}" >/dev/null 2>&1; then
    echo "Error: Docker command not found: ${DOCKER_CMD_ARRAY[0]}"
    exit 1
fi

if ! "${DOCKER_CMD_ARRAY[@]}" image inspect "$DOCKER_IMAGE" >/dev/null 2>&1; then
    echo "Error: Docker image '$DOCKER_IMAGE' not found"
    echo "Build it with: $DOCKER_CMD build --build-arg NOVA_MODE=lite -t $DOCKER_IMAGE -f Dockerfile ."
    exit 1
fi

if [ "$IN_PLACE_LOG" = "true" ]; then
    TEST_DIR="${SKILL_PATH}/execution_records/${RUN_ID}"
    SKILL_PARENT_DIR="$(dirname "$SKILL_PATH")"
    SKILL_BASENAME="$(basename "$SKILL_PATH")"
    TEST_DIR_MOUNT="/app/skill_parent/${SKILL_BASENAME}/execution_records/${RUN_ID}"
    LOG_MOUNT_ARG=(-v "$SKILL_PARENT_DIR:/app/skill_parent")
else
    TEST_BASE_DIR="${EXECUTION_LOGS_DIR}/${SAFE_RISK_LEVEL}/${SAFE_REPO_ID}/${SAFE_SKILL_NAME}"
    TEST_DIR="${TEST_BASE_DIR}/${SAFE_RUN_ID}"
    TEST_DIR_MOUNT="/app/logs/${SAFE_RISK_LEVEL}/${SAFE_REPO_ID}/${SAFE_SKILL_NAME}/${SAFE_RUN_ID}"
    LOG_MOUNT_ARG=(-v "${EXECUTION_LOGS_DIR}:/app/logs")
fi

mkdir -p "$TEST_DIR"

HOST_UID=$(id -u)
HOST_GID=$(id -g)
SAFE_CONTAINER_SUFFIX="$(printf '%s-%s-%s' "$SAFE_SKILL_NAME" "$SAFE_REPO_ID" "$SAFE_RUN_ID" | tr -c 'A-Za-z0-9_.-' '_' | cut -c1-180)"
CONTAINER_NAME="skill-exec-hostauth-${SAFE_CONTAINER_SUFFIX}-$$"

echo "=== Dynamic Skill Executor (host Claude auth) ==="
echo "Skill: $SKILL_NAME"
echo "Repo: $REPO_ID"
echo "Risk: $RISK_LEVEL"
echo "Image: $DOCKER_IMAGE"
echo "Log Dir: $TEST_DIR"
echo "Run ID: $RUN_ID"
echo "Auth: $AUTH_MODE via read-only host credentials"

# Host-side safety net: bound the whole docker run by EXEC_TIMEOUT + 180s, and
# guarantee the container is removed even if `timeout` had to kill the client.
HOST_TIMEOUT=$((TIMEOUT + 180))
trap '"${DOCKER_CMD_ARRAY[@]}" rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true' EXIT

set +e
timeout --kill-after=10s "${HOST_TIMEOUT}s" "${DOCKER_CMD_ARRAY[@]}" run --rm -i \
    --name "$CONTAINER_NAME" \
    --user root \
    --cap-add=SYS_ADMIN \
    --cap-add=NET_ADMIN \
    --security-opt seccomp=unconfined \
    "${LOG_MOUNT_ARG[@]}" \
    -v "${PROJECT_ROOT}/executor/nova_setup.sh:/nova_setup.sh:ro" \
    -v "${PROJECT_ROOT}/executor/smart_monitor.py:/smart_monitor.py:ro" \
    -v "$SKILL_PATH:/skill_source:ro" \
    -v "$CLAUDE_CREDENTIALS_FILE:/host_claude_credentials.json:ro" \
    -w /tmp \
    -e HOST_UID="$HOST_UID" \
    -e HOST_GID="$HOST_GID" \
    -e SKILL_NAME="$SKILL_NAME" \
    -e SAFE_SKILL_NAME="$SAFE_SKILL_NAME" \
    -e REPO_ID="$REPO_ID" \
    -e SAFE_REPO_ID="$SAFE_REPO_ID" \
    -e RISK_LEVEL="$RISK_LEVEL" \
    -e SAFE_RISK_LEVEL="$SAFE_RISK_LEVEL" \
    -e RUN_ID="$RUN_ID" \
    -e SAFE_RUN_ID="$SAFE_RUN_ID" \
    -e DOCKER_IMAGE="$DOCKER_IMAGE" \
    -e AGENT_CLI="$AGENT_CLI" \
    -e AUTH_MODE="$AUTH_MODE" \
    -e USER_PROMPT="$USER_PROMPT" \
    -e TEST_DIR="$TEST_DIR_MOUNT" \
    -e USE_NOVA="$USE_NOVA" \
    -e NOVA_BLOCK="$NOVA_BLOCK" \
    -e NOVA_PROVIDER="$NOVA_PROVIDER" \
    -e NOVA_PROFILE="$NOVA_PROFILE" \
    -e EXEC_TIMEOUT="$TIMEOUT" \
    "$DOCKER_IMAGE" bash -s <<'CONTAINER_SCRIPT'
set -euo pipefail

if ! getent group appuser >/dev/null; then
    groupadd -g "$HOST_GID" appuser 2>/dev/null || groupadd appuser
else
    groupmod -g "$HOST_GID" appuser 2>/dev/null || true
fi

if ! id appuser >/dev/null 2>&1; then
    useradd -m -u "$HOST_UID" -g appuser -s /bin/bash appuser
else
    usermod -u "$HOST_UID" -g appuser appuser 2>/dev/null || true
fi

APPUSER_HOME="/home/appuser"
export HOME="$APPUSER_HOME"
export APPUSER_HOME
export USER="appuser"
export CLAUDE_PROJECT_DIR="$APPUSER_HOME"

mkdir -p "$TEST_DIR" "$APPUSER_HOME/.claude/skills" "$APPUSER_HOME/.claude/todos" "$APPUSER_HOME/.claude/cache" "$APPUSER_HOME/.claude/debug"
cp /host_claude_credentials.json "$APPUSER_HOME/.claude/.credentials.json"
echo '{"hasCompletedOnboarding": true}' > "$APPUSER_HOME/.claude.json"
cp -r /skill_source "$APPUSER_HOME/.claude/skills/$SAFE_SKILL_NAME"

chown -R appuser:appuser "$APPUSER_HOME/.claude" "$APPUSER_HOME/.claude.json" "$TEST_DIR"
chmod 700 "$APPUSER_HOME/.claude"
chmod 600 "$APPUSER_HOME/.claude/.credentials.json"

export NOVA_SESSION_ID="hostauth_${SAFE_SKILL_NAME}_$(date +%Y%m%d_%H%M%S)"
export NOVA_BLOCK_MODE="$([ "$NOVA_BLOCK" = "true" ] && echo "true" || echo "false")"
if [ "$USE_NOVA" = "true" ]; then
    if [ "$NOVA_BLOCK" = "true" ] && [ "${NOVA_PROFILE}" = "record" ]; then
        NOVA_PROFILE="guard"
    fi
    export NOVA_PROFILE
    /nova_setup.sh "$APPUSER_HOME" "$NOVA_PROFILE"
    export NOVA_REPORT_DIR="$TEST_DIR/nova-tracer"
    mkdir -p "$NOVA_REPORT_DIR"
    chown -R appuser:appuser "$NOVA_REPORT_DIR"
    echo "[NOVA] Initialized: provider=${NOVA_PROVIDER}, profile=${NOVA_PROFILE}, report_dir=${NOVA_REPORT_DIR}"
fi

python3 - "$TEST_DIR/metadata.json" <<'PY'
import json
import os
import sys
from datetime import datetime, timezone

path = sys.argv[1]
data = {
    "skill_name": os.environ.get("SKILL_NAME", ""),
    "safe_skill_name": os.environ.get("SAFE_SKILL_NAME", ""),
    "repo_id": os.environ.get("REPO_ID", ""),
    "safe_repo_id": os.environ.get("SAFE_REPO_ID", ""),
    "risk_level": os.environ.get("RISK_LEVEL", ""),
    "safe_risk_level": os.environ.get("SAFE_RISK_LEVEL", ""),
    "run_id": os.environ.get("RUN_ID", ""),
    "safe_run_id": os.environ.get("SAFE_RUN_ID", ""),
    "docker_image": os.environ.get("DOCKER_IMAGE", ""),
    "agent_cli": os.environ.get("AGENT_CLI", ""),
    "auth_mode": os.environ.get("AUTH_MODE", ""),
    "user": "appuser",
    "home": os.environ.get("APPUSER_HOME", ""),
    "timeout_seconds": os.environ.get("EXEC_TIMEOUT", ""),
    "use_nova": os.environ.get("USE_NOVA", ""),
    "nova_block": os.environ.get("NOVA_BLOCK", ""),
    "nova_provider": os.environ.get("NOVA_PROVIDER", ""),
    "nova_profile": os.environ.get("NOVA_PROFILE", ""),
    "start_time": datetime.now(timezone.utc).isoformat(),
}
with open(path, "w", encoding="utf-8") as fh:
    json.dump(data, fh, indent=2)
    fh.write("\n")
PY
chown appuser:appuser "$TEST_DIR/metadata.json"

PROMPT_FILE="/tmp/skill_user_prompt.txt"
printf '%s' "$USER_PROMPT" > "$PROMPT_FILE"
chown appuser:appuser "$PROMPT_FILE"

echo "[Monitor] Starting tcpdump..."
tcpdump -i any -w "$TEST_DIR/network.pcap" -s 0 2>"$TEST_DIR/tcpdump.stderr" &
TCPDUMP_PID=$!
sleep 1
if ! kill -0 "$TCPDUMP_PID" 2>/dev/null; then
    echo "[Monitor] tcpdump failed to start; continuing without packet capture"
    TCPDUMP_PID=""
fi

cleanup() {
    if [ -n "${TCPDUMP_PID:-}" ]; then
        kill -TERM "$TCPDUMP_PID" 2>/dev/null || true
        for _ in 1 2 3 4 5; do
            kill -0 "$TCPDUMP_PID" 2>/dev/null || break
            sleep 1
        done
        kill -KILL "$TCPDUMP_PID" 2>/dev/null || true
        wait "$TCPDUMP_PID" 2>/dev/null || true
        TCPDUMP_PID=""
    fi
}
trap cleanup EXIT

echo "[Monitor] Creating baseline snapshot..."
python3 /smart_monitor.py snapshot /tmp/fs_state.json "$APPUSER_HOME"

echo "=========================================="
echo "Executing Skill (timeout: ${EXEC_TIMEOUT}s)"
echo "=========================================="

STRACE_LOG="$TEST_DIR/strace.log"
STRACE_OPTS="-f -s 2000 -e trace=open,openat,creat,write,unlink,rename,mkdir,rmdir,execve,connect,accept,sendto,recvfrom"

set +e
strace $STRACE_OPTS -o "$STRACE_LOG" \
    su appuser -c "cd '$APPUSER_HOME' && timeout '${EXEC_TIMEOUT}s' claude --print --dangerously-skip-permissions \"\$(cat '$PROMPT_FILE')\"" \
    </dev/null 2>&1 | tee -a "$TEST_DIR/claude_output.txt"
PIPE_STATUS=("${PIPESTATUS[@]}")
set -e
EXIT_CODE="${PIPE_STATUS[0]}"

if [ "$EXIT_CODE" -eq 124 ]; then
    echo "Warning: Execution timeout (${EXEC_TIMEOUT}s)" | tee -a "$TEST_DIR/claude_output.txt"
else
    echo "Execution complete (exit code: $EXIT_CODE)" | tee -a "$TEST_DIR/claude_output.txt"
fi

python3 - "$TEST_DIR/metadata.json" "$EXIT_CODE" <<'PY'
import json
import sys
from datetime import datetime, timezone

path, exit_code = sys.argv[1], int(sys.argv[2])
with open(path, "r", encoding="utf-8") as fh:
    data = json.load(fh)
data["exit_code"] = exit_code
data["end_time"] = datetime.now(timezone.utc).isoformat()
with open(path, "w", encoding="utf-8") as fh:
    json.dump(data, fh, indent=2)
    fh.write("\n")
PY

cleanup
trap - EXIT

echo "[Monitor] Analyzing file changes..."
python3 /smart_monitor.py diff /tmp/fs_state.json "$APPUSER_HOME" "$TEST_DIR"

if [ "$USE_NOVA" = "true" ]; then
    if [ -d "$APPUSER_HOME/.nova-tracer" ]; then
        rm -rf "$TEST_DIR/nova-tracer"
        mkdir -p "$TEST_DIR/nova-tracer"
        cp -a "$APPUSER_HOME/.nova-tracer/." "$TEST_DIR/nova-tracer/" 2>/dev/null || true
    fi
    echo "[NOVA] Report files:"
    find "$TEST_DIR/nova-tracer" -maxdepth 3 -type f -printf '  %P\n' 2>/dev/null || true
fi

chown -R "$HOST_UID:$HOST_GID" "$TEST_DIR"

echo "=========================================="
echo "Execution Complete"
echo "=========================================="
exit "$EXIT_CODE"
CONTAINER_SCRIPT
DOCKER_RC=$?
set -e

if [ "$DOCKER_RC" -eq 124 ] || [ "$DOCKER_RC" -eq 137 ]; then
    echo "Warning: host-side timeout fired after ${HOST_TIMEOUT}s; container force-removed"
fi

trap - EXIT
echo ""
echo "Done: $TEST_DIR"
exit "$DOCKER_RC"
