#!/bin/bash
#
# Script 1: Crawl skill data
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib.sh"

init_config

log_info "=========================================="
log_info "Step 1: Crawl Skill Data"
log_info "=========================================="

# Check if skip is requested
if [ "$SKIP_CRAWL" = "true" ]; then
    log_warn "Skipping crawl (SKIP_CRAWL=true)"
    exit 0
fi

cd "$PROJECT_ROOT"

# Crawl skills.rest
CRAWL_FAILED=false
REST_NEW=0
MP_NEW=0
MERGE_TOTAL=0

if [ "${SKIP_REST_CRAWL:-false}" = "true" ]; then
    log_warn "Skipping skills.rest crawl (SKIP_REST_CRAWL=true)"
else
if REST_OUTPUT=$(python3 -c "
import sys
sys.path.insert(0, '.')
from crawler.crawler import SkillsRestCrawler, Config

config = Config()
crawler = SkillsRestCrawler(config)
count = crawler.run()
print(f'SkillsRest: {count} new items')
" 2>&1); then
    echo "$REST_OUTPUT"
    REST_NEW=$(echo "$REST_OUTPUT" | sed -n 's/^SkillsRest: \([0-9][0-9]*\) new items$/\1/p' | tail -1)
    REST_NEW=${REST_NEW:-0}
    log_success "SkillsRest crawl complete"
else
    echo "$REST_OUTPUT"
    log_error "SkillsRest crawl failed"
    CRAWL_FAILED=true
fi
fi

# Crawl skillsmp (if API key available)
if [ -n "$SKILLSMP_API_KEY" ]; then
    if MP_OUTPUT=$(python3 -c "
import sys
sys.path.insert(0, '.')

from crawler.crawler import SkillsmpCrawler, Config

config = Config()
crawler = SkillsmpCrawler(config)
count = crawler.run()
print(f'SkillsMP: {count} new items')
" 2>&1); then
        echo "$MP_OUTPUT"
        MP_NEW=$(echo "$MP_OUTPUT" | sed -n 's/^SkillsMP: \([0-9][0-9]*\) new items$/\1/p' | tail -1)
        MP_NEW=${MP_NEW:-0}
        log_success "SkillsMP crawl complete"
    else
        echo "$MP_OUTPUT"
        log_warn "SkillsMP crawl failed"
        CRAWL_FAILED=true
    fi
else
    log_warn "SKILLSMP_API_KEY not set, skipping SkillsMP crawl"
fi

# Merge data
if MERGE_OUTPUT=$(python3 -c "
import sys
sys.path.insert(0, '.')
from crawler.crawler import DataMerger, Config

config = Config()
merger = DataMerger(config)
result = merger.merge()
print(f'Merge: {result}')
" 2>&1); then
    echo "$MERGE_OUTPUT"
    MERGE_TOTAL=$(echo "$MERGE_OUTPUT" | python3 -c "
import ast, re, sys
text = sys.stdin.read()
match = re.search(r'Merge: (\\{.*\\})', text)
if not match:
    print(0)
else:
    try:
        print(int(ast.literal_eval(match.group(1)).get('total', 0)))
    except Exception:
        print(0)
")
    log_success "Data merge complete"
else
    echo "$MERGE_OUTPUT"
    log_error "Data merge failed"
    CRAWL_FAILED=true
fi

if [ "$CRAWL_FAILED" = "true" ] || { [ "${REQUIRE_CRAWL_ITEMS:-true}" = "true" ] && [ "$REST_NEW" -eq 0 ] && [ "$MP_NEW" -eq 0 ] && [ "$MERGE_TOTAL" -eq 0 ]; }; then
    log_error "Step 1 failed"
    log_error "No crawl items were collected. Check SKILLSMP_API_KEY or Cloudflare/API access."
    exit 1
fi

log_success "Step 1 complete!"
