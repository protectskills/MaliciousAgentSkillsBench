#!/bin/bash
#
# Script 4: Static security scan
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib.sh"

init_config

log_info "=========================================="
log_info "Step 4: Static Security Scan"
log_info "=========================================="

cd "$PROJECT_ROOT"

# Check for ZIP files
zip_count=$(find "$WORKSPACE_DIR/zip" -name "*.zip" 2>/dev/null | wc -l)
if [ "$zip_count" -eq 0 ]; then
    log_error "No ZIP files found in $WORKSPACE_DIR/zip"
    log_error "Please run step 3 (download) first"
    exit 1
fi

log_info "Found $zip_count ZIP files"

# Run scanner
export WORKSPACE_DIR SCAN_LIMIT
python3 - <<'PY'
import os
import sys
sys.path.insert(0, '.')
from scanner.scanner import RepoSecurityScanner, Config
from pathlib import Path

config = Config()
scanner = RepoSecurityScanner(config)

# Get all ZIP files
workspace_dir = Path(os.environ['WORKSPACE_DIR'])
zip_files = list((workspace_dir / 'zip').glob('*.zip'))
zip_files.sort(key=lambda x: int(''.join(filter(str.isdigit, x.stem))) if ''.join(filter(str.isdigit, x.stem)) else 0)

print(f'ZIPS to scan: {len(zip_files)}')

# Scan
scan_limit = os.environ.get('SCAN_LIMIT', '0')
if not scan_limit.isdigit():
    print(f'Invalid SCAN_LIMIT: {scan_limit}', file=sys.stderr)
    sys.exit(1)
result = scanner.scan_all(limit=int(scan_limit))

print(f"\nScan Results:")
print(f"Total: {result['total']}")
print(f"Scanned: {result['scanned']}")
print(f"Skipped: {result['skipped']}")
print(f"Failed: {result['failed']}")
print(f"\nRisk Distribution:")
for risk, count in result['by_risk'].items():
    if count > 0:
        print(f"  {risk}: {count}")
PY

log_success "Static scan complete!"
log_info "Reports in: $WORKSPACE_DIR/static/{critical,high,medium,low,safe}/"
