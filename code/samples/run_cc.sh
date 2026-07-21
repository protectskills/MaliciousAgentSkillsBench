#!/bin/bash
#
# Run the CC (LLM) security triage on the bundled malicious sample(s).
# Prints the verdict (SAFE / SUSPICIOUS / MALICIOUS); results land under
# scan_results/{SAFE,SUSPICIOUS,MALICIOUS}/. Needs a Claude Code login or an
# API key (see the main README for the API-key / alternate-model setup).
#
set -e
cd "$(dirname "$0")/.."   # -> code/
queue="$(mktemp)"
for d in samples/*/; do
    [ -f "${d}SKILL.md" ] || continue
    name="$(basename "$d")"
    printf '%s|%s|analyze|%s|critical\n' "$name" "$(pwd)/$d" "$name" >> "$queue"
done
bash analyzer/cc_analyzer.sh "$queue"
rm -f "$queue"
