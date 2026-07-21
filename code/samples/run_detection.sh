#!/bin/bash
#
# Reproduce end-to-end detection on the bundled defanged malicious sample.
# Thin wrapper around the existing pipeline; evidence lands under workspace/dynamic/.
#
set -e
cd "$(dirname "$0")/.."   # -> code/
exec python3 helper.py exec-dir samples/malicious "$@"
