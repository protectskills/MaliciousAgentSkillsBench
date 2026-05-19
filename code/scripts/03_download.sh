#!/bin/bash
#
# Script 3: Download repositories
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib.sh"

init_config

log_info "=========================================="
log_info "Step 3: Download Repositories"
log_info "=========================================="

cd "$PROJECT_ROOT"

# Check mapping files
if [ ! -f "$DATA_DIR/repo_skill_mapping.json" ] && [ ! -f "$DATA_DIR/skillsmp_repo_mapping.json" ]; then
    log_error "Mapping files not found: $DATA_DIR/repo_skill_mapping.json or $DATA_DIR/skillsmp_repo_mapping.json"
    log_error "Please run step 2 (generate mapping) first"
    exit 1
fi

# Run downloader
export DOWNLOAD_LIMIT DATA_DIR STRICT_DOWNLOAD
python3 - <<'PY'
import os
import sys
import json
sys.path.insert(0, '.')
from scanner.scanner import RepoDownloader, Config

config = Config()
downloader = RepoDownloader(config)

# Load mapping
mapping = []
data_dir = os.environ['DATA_DIR']
for path in [f'{data_dir}/repo_skill_mapping.json', f'{data_dir}/skillsmp_repo_mapping.json']:
    try:
        with open(path, 'r') as f:
            mapping.extend(json.load(f))
    except FileNotFoundError:
        pass

# Prepare repo info with id_prefix
for item in mapping:
    item['id_prefix'] = item.get('id_prefix', '')

# Download
download_limit = os.environ.get('DOWNLOAD_LIMIT', '0')
if not download_limit.isdigit():
    print(f'Invalid DOWNLOAD_LIMIT: {download_limit}', file=sys.stderr)
    sys.exit(1)
result = downloader.download_all(mapping, limit=int(download_limit))

print(f"Total: {result['total']}")
print(f"Success: {result['success']}")
print(f"Failed: {result['failed']}")
print(f"Skipped: {result['skipped']}")

usable = result['success'] + result['skipped']
if result['total'] == 0 or usable == 0:
    print('No repositories are available for scanning after download.', file=sys.stderr)
    sys.exit(1)
if result['failed'] > 0 and os.environ.get('STRICT_DOWNLOAD', 'false').lower() == 'true':
    print('STRICT_DOWNLOAD=true and at least one repository failed.', file=sys.stderr)
    sys.exit(1)
PY

log_success "Download complete!"
log_info "ZIP files: $WORKSPACE_DIR/zip/"
