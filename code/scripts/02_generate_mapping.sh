#!/bin/bash
#
# Script 2: Generate mapping from crawled data
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib.sh"

init_config

log_info "=========================================="
log_info "Step 2: Generate Repository Mapping"
log_info "=========================================="

cd "$PROJECT_ROOT"

# Check if merged data exists
if [ ! -f "$DATA_DIR/all_skills_data.json" ]; then
    log_error "Merged data not found: $DATA_DIR/all_skills_data.json"
    log_error "Please run step 1 (crawl) first"
    exit 1
fi

# Generate mappings
export DATA_DIR
python3 - <<'PY'
import json
import os
import sys
from pathlib import Path
from collections import defaultdict

output_dir = Path(os.environ['DATA_DIR'])
data_file = output_dir / 'all_skills_data.json'

with open(data_file, 'r') as f:
    all_skills = json.load(f)

# Group by repo
repo_skills = defaultdict(list)
for skill in all_skills:
    source_url = skill.get('source_url', '')
    if not source_url:
        continue

    # Extract repo info
    from urllib.parse import urlparse
    parsed = urlparse(source_url)
    path_parts = [p for p in parsed.path.split('/') if p]

    if len(path_parts) >= 2:
        repo = f'{path_parts[0]}/{path_parts[1]}'

        # Generate ID prefix
        source = skill.get('data_source', '')
        if source == 'skills.rest':
            prefix = 'rest'
            id_key = str(skill.get('id', ''))
        elif source == 'skillsmp.com':
            prefix = 'smp'
            id_key = str(skill.get('id', ''))
        else:
            continue

        repo_skills[(repo, prefix)].append({
            'name': skill.get('name', ''),
            'slug': skill.get('slug', ''),
            'skill_id': id_key
        })

# Generate mapping files
rest_mapping = []
smp_mapping = []
repo_id = 0

for (repo, prefix), skills in repo_skills.items():
    mapping = {
        'repo_id': repo_id,
        'repo': repo,
        'id_prefix': f'{prefix}_',
        'download_url': f'https://github.com/{repo}/archive/main.zip',
        'branch': 'main',
        'total_skills': len(skills),
        'skills': skills
    }

    if prefix == 'rest':
        rest_mapping.append(mapping)
    else:
        smp_mapping.append(mapping)

    repo_id += 1

# Save mappings
with open(output_dir / 'repo_skill_mapping.json', 'w') as f:
    json.dump(rest_mapping, f, indent=2)

with open(output_dir / 'skillsmp_repo_mapping.json', 'w') as f:
    json.dump(smp_mapping, f, indent=2)

print(f'Generated {len(rest_mapping)} REST mappings')
print(f'Generated {len(smp_mapping)} SkillsMP mappings')
print(f'Total repos: {repo_id}')
PY

log_success "Repository mapping generated!"
log_info "REST mapping: $DATA_DIR/repo_skill_mapping.json"
log_info "SkillsMP mapping: $DATA_DIR/skillsmp_repo_mapping.json"
