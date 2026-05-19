#!/bin/bash
#
# NOVA setup for the dynamic skill sandbox.
#
# Usage:
#   nova_setup.sh <appuser_home> [record|scan|guard|monitor|block]
#
# Profiles:
#   record - real Nova-tracer session/tool recording only; no scan, no block
#   scan   - record + nova-hunting post-tool detection; no block
#   guard  - scan + PreToolUse blocking for Bash/Write/Edit
#
# Legacy compatibility:
#   monitor -> record
#   block   -> guard
#

set -euo pipefail

APPUSER_HOME="${1:-}"
PROFILE="${2:-record}"
case "$PROFILE" in
    monitor) PROFILE="record" ;;
    block) PROFILE="guard" ;;
esac

case "$PROFILE" in
    record|scan|guard) ;;
    *)
        echo "[NOVA] Unknown profile '$PROFILE' (expected record, scan, or guard)"
        exit 1
        ;;
esac

if [ -z "$APPUSER_HOME" ]; then
    echo "Usage: $0 <appuser_home> [record|scan|guard]"
    exit 1
fi

CLAUDE_DIR="$APPUSER_HOME/.claude"
SETTINGS_FILE="$CLAUDE_DIR/settings.json"
mkdir -p "$CLAUDE_DIR"

NOVA_MODE_INSTALLED="$(cat /opt/nova-tracer/nova_mode 2>/dev/null || echo none)"

write_tracer_config() {
    local enable_keywords="$1"
    local enable_semantics="$2"
    local enable_llm="$3"

    cat > /opt/nova-tracer/config/nova-config.yaml <<EOF
llm_provider: anthropic
model: claude-3-5-haiku-20241022
enable_keywords: $enable_keywords
enable_semantics: $enable_semantics
enable_llm: $enable_llm
semantic_threshold: 0.7
llm_threshold: 0.7
llm_timeout: 10
max_content_length: 50000
min_severity: low
rule_files:
  - instruction_override.nov
  - roleplay_jailbreak.nov
  - encoding_obfuscation.nov
  - context_manipulation.nov
debug: false
log_file: ""
dangerous_patterns:
  - pattern: '\\bchmod\\s+777'
    reason: "Overly permissive chmod"
    enabled: false
protected_files:
  - pattern: '(^|/)\\.env$'
    reason: "Environment file"
    enabled: false
  - pattern: '(^|/)\\.env\\.local$'
    reason: "Local environment file"
    enabled: false
  - pattern: '(^|/)\\.ssh/'
    reason: "SSH directory"
    enabled: false
dangerous_content_patterns: []
EOF

    cat > /opt/nova-tracer/config/nova-tracer.yaml <<EOF
ai_summary_enabled: false
output_truncation_kb: 10
custom_rules_dir: rules/
EOF
}

write_real_tracer_settings() {
    local include_guard="$1"

    if [ "$include_guard" = "true" ]; then
        cat > "$SETTINGS_FILE" <<'EOF'
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "",
        "hooks": [
          {"type": "command", "command": "python3 /opt/nova-tracer/hooks/session-start.py"}
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "matcher": "",
        "hooks": [
          {"type": "command", "command": "python3 /opt/nova-tracer/hooks/user-prompt-capture.py"}
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {"type": "command", "command": "python3 /opt/nova-tracer/hooks/pre-tool-guard.py"}
        ]
      },
      {
        "matcher": "Write",
        "hooks": [
          {"type": "command", "command": "python3 /opt/nova-tracer/hooks/pre-tool-guard.py"}
        ]
      },
      {
        "matcher": "Edit",
        "hooks": [
          {"type": "command", "command": "python3 /opt/nova-tracer/hooks/pre-tool-guard.py"}
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "*",
        "hooks": [
          {"type": "command", "command": "python3 /opt/nova-tracer/hooks/post-tool-nova-guard.py", "timeout": 120}
        ]
      }
    ],
    "SessionEnd": [
      {
        "matcher": "",
        "hooks": [
          {"type": "command", "command": "python3 /opt/nova-tracer/hooks/session-end.py"}
        ]
      }
    ]
  },
  "hookSettings": {
    "novaProvider": "tracer",
    "novaProfile": "guard",
    "blockDangerousCommands": true,
    "alertOnSuspiciousActivity": true
  }
}
EOF
    else
        cat > "$SETTINGS_FILE" <<EOF
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "",
        "hooks": [
          {"type": "command", "command": "python3 /opt/nova-tracer/hooks/session-start.py"}
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "matcher": "",
        "hooks": [
          {"type": "command", "command": "python3 /opt/nova-tracer/hooks/user-prompt-capture.py"}
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "*",
        "hooks": [
          {"type": "command", "command": "python3 /opt/nova-tracer/hooks/post-tool-nova-guard.py", "timeout": 120}
        ]
      }
    ],
    "SessionEnd": [
      {
        "matcher": "",
        "hooks": [
          {"type": "command", "command": "python3 /opt/nova-tracer/hooks/session-end.py"}
        ]
      }
    ]
  },
  "hookSettings": {
    "novaProvider": "tracer",
    "novaProfile": "$PROFILE",
    "blockDangerousCommands": false,
    "alertOnSuspiciousActivity": true
  }
}
EOF
    fi
}

if [ "$NOVA_MODE_INSTALLED" != "none" ] && [ -d /opt/nova-tracer/hooks ]; then
    case "$PROFILE" in
        record)
            write_tracer_config false false false
            write_real_tracer_settings false
            ;;
        scan)
            write_tracer_config true true false
            write_real_tracer_settings false
            ;;
        guard)
            write_tracer_config true true false
            write_real_tracer_settings true
            ;;
    esac
    chown -R appuser:appuser "$CLAUDE_DIR" /opt/nova-tracer
    echo "[NOVA] Setup complete (provider: tracer, profile: $PROFILE)"
else
    echo "[NOVA] Not installed (NOVA_MODE=none)"
fi
