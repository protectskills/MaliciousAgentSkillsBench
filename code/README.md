# MaliciousAgentSkillsBench Code

**This is the code component of [MaliciousAgentSkillsBench](../) - a security benchmark for Claude Code Agent Skills.**

A reproducible security analysis pipeline for Claude Code Skills. Performs static code analysis, optional LLM-assisted triage, and dynamic execution monitoring.

## Overview

This project provides an end-to-end security scanning pipeline for Claude Code Skills:

1. **Crawl** - Fetch skill metadata from SkillsMP by default; skills.rest remains supported when accessible
2. **Download** - Download skill repositories from GitHub
3. **Static Scan** - Rule-based security scanning
4. **Dynamic Execute** - Execute selected skills in a monitored Docker sandbox
5. **LLM Triage** - Optional Claude Code post-hoc audit of static-scan reports (disabled by default)

## Features

- Multi-platform crawler (skills.rest, skillsmp.com)
- Concurrent repository downloading with branch fallback
- Static security scanning with configurable rules
- Optional LLM-assisted triage using Claude Code
- Dynamic execution in isolated Docker sandbox
- Comprehensive monitoring (strace, tcpdump, Nova-tracer)
- Configurable pipeline with step-by-step execution

## Project Structure

```
code/                                 # This directory
├── analyzer/           # Optional Claude Code triage module
│   ├── cc_analyzer.sh
│   └── prompts/         # Audit prompts
├── crawler/            # Web crawler module
│   └── crawler.py
├── data/               # Crawled data (gitignored): all_skills_data.json,
│                       #   repo_skill_mapping.json, skillsmp_repo_mapping.json
├── executor/           # Dynamic execution module
│   ├── batch_runner.py
│   ├── nova-tracer/     # Vendored real Nova-tracer hooks, rules, reports
│   ├── nova_setup.sh
│   ├── run_skill.sh
│   ├── run_skill_hostauth.sh
│   └── smart_monitor.py
├── scanner/            # Static scanner module
│   ├── scanner.py
│   └── skill-security-scan/
├── scripts/            # Pipeline control scripts
│   ├── run_pipeline.sh  # Scripted step runner
│   ├── lib.sh           # Shared functions
│   ├── 01_crawl.sh
│   ├── 02_generate_mapping.sh
│   ├── 03_download.sh
│   ├── 04_scan.sh
│   ├── 05_gen_run_queue.sh
│   ├── 06_execute.sh
│   ├── 07_gen_cc_queue.sh
│   └── 08_cc_analyze.sh
├── tasks/              # Task queues (gitignored): run_queue.txt, cc_queue.txt,
│                       #   run_queue_state.jsonl, local_skills_queue.txt
├── utils/              # Utility modules
│   ├── config_loader.py
│   └── path_helper.py
├── workspace/          # Working directory (gitignored)
│   ├── zip/            # Downloaded repository archives
│   ├── repo/           # Extracted repositories
│   ├── static/         # Repo-level static scan reports by risk
│   └── dynamic/        # Skill-level dynamic execution logs
├── scan_results/       # Optional Claude Code triage results (gitignored)
├── logs/               # Helper.py build logs (gitignored)
├── helper.py           # Interactive reproduction CLI (main entry point)
├── config.yaml         # Configuration file
├── .env.example        # Environment template
├── nova-requirements.txt  # Real Nova-tracer full-mode scanner dependency
├── Dockerfile          # Docker sandbox image
├── DOCKER_BUILD.md     # Docker build guide
└── requirements.txt    # Python dependencies
```

## Installation

### Prerequisites

**For crawl/download/static scan:**
- Python 3.10+
- GitHub token (optional, but recommended for public repository downloads at scale)

**For LLM triage and dynamic execution:**
- Claude Code CLI login

**For Docker-based execution:**
- Docker (required for sandboxed skill execution)

**For default crawl path:**
- SkillsMP API key

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd MaliciousAgentSkillsBench/code
```

2. Install Python dependencies (for local analysis):
```bash
pip install -r requirements.txt
```

3. Build Docker sandbox image (for dynamic execution):
```bash
docker build --build-arg NOVA_MODE=lite -t claude-skill-sandbox -f Dockerfile .
```

See [DOCKER_BUILD.md](DOCKER_BUILD.md) for `none`, `lite`, and `full` build
modes.

4. Configure and run through the interactive helper:
```bash
python3 helper.py
```

The menu provides the common workflow: initialize `.env`, check dependencies
and credentials, build the Docker sandbox, run the default small-batch
experiment, inspect status, adjust common configuration, and clean runtime
outputs. It also offers a continuation prompt after dynamic execution so you
can run more pending skills without repeating crawl/download/scan.

## Usage

### Run Complete Pipeline

For the default small-batch experiment, use SkillsMP plus the local Claude Code
login. The helper is the recommended entry point:

```bash
python3 helper.py
```

If larger batches are needed, increase `SKILLSMP_MAX_ITEMS`, `DOWNLOAD_LIMIT`,
`SCAN_LIMIT`, execution limit, and worker counts.

The paper's confirmed malicious labels come from static candidate detection,
sandboxed behavioral verification, and independent human review. Claude Code
analysis is an optional triage aid for reproduction and is disabled by default;
dynamic evidence remains the important artifact.

The underlying scripts can also be run manually:

```bash
export SKILLSMP_API_KEY=your_skillsmp_api_key_here
export SKIP_REST_CRAWL=true
export SKILLSMP_SEARCH_CHARS=a
export SKILLSMP_MAX_ITEMS=30
export SKILLSMP_PAGE_LIMIT=30
export SKILLSMP_MAX_PAGES_PER_QUERY=1

docker build --build-arg NOVA_MODE=lite -t claude-skill-sandbox -f Dockerfile .

bash scripts/01_crawl.sh
DOWNLOAD_LIMIT=5 SCAN_LIMIT=5 bash scripts/02_generate_mapping.sh
DOWNLOAD_LIMIT=5 bash scripts/03_download.sh
SCAN_LIMIT=5 bash scripts/04_scan.sh
RUN_QUEUE_SOURCE=static RUN_FROM_RISKS="critical high medium low safe" bash scripts/05_gen_run_queue.sh
SKILL_EXECUTOR=hostauth EXEC_WORKERS=1 RUN_QUEUE_LIMIT=1 USE_NOVA=true NOVA_PROFILE=record EXEC_TIMEOUT=240 bash scripts/06_execute.sh
```

To run optional Claude Code analysis after dynamic execution:

```bash
CC_RISK_LEVELS="low medium high critical safe" CC_QUEUE_LIMIT=3 bash scripts/07_gen_cc_queue.sh
CC_MODEL=claude-sonnet-4-6 CC_JOBS=1 bash scripts/08_cc_analyze.sh
```

Step 5 uses `RUN_PROMPT_TEMPLATE` to build each dynamic execution prompt. The
default asks Claude to use the target skill, design and run a sandboxed test,
and create temporary files or helper scripts when useful. Override it for
stricter or larger experiments; `{skill_name}` is replaced with the current
skill name.

The generated `tasks/run_queue.txt` contains all discovered execution
candidates. `RUN_QUEUE_LIMIT` controls how many pending entries are executed in
one run, and `tasks/run_queue_state.jsonl` records completed and failed tasks so
later runs can skip completed entries.

`EXEC_TIMEOUT` is the inner Claude CLI wall-clock budget enforced by `timeout`
inside the container; it does not include the ~30-60s of container setup
(user/credential mount, NOVA setup, tcpdump start, baseline snapshot). The
host-side executor wraps the whole `docker run` in `EXEC_TIMEOUT + 180s` and
force-removes the container if that fires, so a hung container cannot block
subsequent skills. The helper default is 240s (suitable for small batches);
bump to 300+ for slow networks or heavy skills. Bare `scripts/06_execute.sh`
falls back to the `config.yaml` `executor.timeout` value (900s) when no env
override is supplied.

If a skill reaches `EXEC_TIMEOUT` after NOVA has already produced an HTML
report, the run is recorded as captured artifacts rather than a failed
dynamic-monitoring run; entries with no substantive Claude output are marked
separately. Set `RETRY_TIMEOUT_ARTIFACTS=true` with a larger `EXEC_TIMEOUT`
to retry those entries.

For large batches (default: more than `EXEC_QUIET_THRESHOLD=10` pending
skills), the batch runner switches to quiet mode automatically: each skill's
subprocess output is redirected to `logs/exec/<timestamp>_<id>_<skill>.log`
and a single status line per skill is printed to the terminal, formatted as
`[i/total] <repo>/<skill> (<risk>) -> <status> (<duration>)`.

`scripts/run_pipeline.sh` remains available as a scripted step runner, but the
helper is the recommended entry point for new reproductions.

### Run Individual Steps

```bash
# Step 1: Crawl skill data
./scripts/01_crawl.sh

# Step 2: Generate repository mapping
./scripts/02_generate_mapping.sh

# Step 3: Download repositories
./scripts/03_download.sh

# Step 4: Static security scan
./scripts/04_scan.sh

# Step 5: Generate execution queue from static scan reports
./scripts/05_gen_run_queue.sh

# Step 6: Dynamic execution
./scripts/06_execute.sh

# Step 7: Optional LLM triage queue
./scripts/07_gen_cc_queue.sh

# Step 8: Optional LLM triage
./scripts/08_cc_analyze.sh
```

### Run One Skill with Host Claude Login

For local reproduction, use the host-auth executor.
It runs Claude Code inside the Docker sandbox using a read-only mounted host
Claude credential file, then writes per-run monitoring artifacts under a unique
run directory.

Treat the mounted Claude credential as sensitive. Run untrusted skills with a
disposable login/account when possible; the sandboxed process can read the
credential while executing.

This runner is an instrumentation sandbox, not a strong isolation boundary: it
uses Docker capabilities such as `SYS_ADMIN`, `NET_ADMIN`, and an unconfined
seccomp profile so strace, tcpdump, and hook recording can work. Run
untrusted or malicious skills from a disposable VM/host and a disposable
Claude login.

```bash
# Build the sandbox with NOVA hook recording
docker build --build-arg NOVA_MODE=lite -t claude-skill-sandbox -f Dockerfile .

# Execute one real skill
PROJECT_ROOT=$PWD \
EXECUTION_LOGS_DIR=$PWD/workspace/dynamic \
CLAUDE_CREDENTIALS_FILE="$HOME/.claude/.credentials.json" \
EXEC_TIMEOUT=240 \
USE_NOVA=true \
NOVA_BLOCK=false \
NOVA_PROFILE=record \
./executor/run_skill_hostauth.sh \
  data-analysis \
  "$HOME/.claude/skills/data-analysis" \
  "Use the data-analysis skill to design and run a sandboxed test for this skill." \
  local_real_skill \
  low \
  false
```

Expected artifacts:

```text
workspace/dynamic/<risk>/<repo>/<skill>/<run-id>/
├── claude_output.txt
├── strace.log
├── network.pcap
├── filesystem_changes.json
├── metadata.json
└── nova-tracer/
    ├── sessions/*.jsonl
    └── reports/*.html
```

Treat NOVA sessions, HTML reports, Claude output, packet captures, and
filesystem traces as sensitive experiment logs. They may include prompts, tool
inputs/outputs, local paths, or secret-like strings printed by tools.

Current provider support is `AGENT_CLI=claude` with `AUTH_MODE=host_claude`.
The legacy `run_skill.sh` API-token executor remains for compatibility, but the
default batch path uses `run_skill_hostauth.sh`; API-token batch execution is
not the recommended reproduction path.

NOVA build and runtime modes:

- `NOVA_MODE=lite` vendors real Nova-tracer and installs only record/report
  dependencies. Use this with `NOVA_PROFILE=record`.
- `NOVA_MODE=full` additionally installs `nova-hunting`, which provides the
  `nova.core` scanner imported by Nova-tracer. Torch selection is controlled by
  `NOVA_TORCH_SPEC` and `NOVA_TORCH_INDEX_URL`.
- `NOVA_PROFILE=record` is the default and only records session, prompt, skill,
  MCP, and tool activity. It does not register `PreToolUse` blocking hooks.
- `NOVA_PROFILE=scan` records plus runs post-tool NOVA detection and emits
  warnings into Claude hook output. It still does not block pre-execution.
- `NOVA_PROFILE=guard` records, scans, and registers upstream `PreToolUse`
  blocking for Bash/Write/Edit. This is available for experiments but is not
  the default reproduction path.

`executor/nova-tracer/` is a vendored runtime subset of Nova-tracer and is
distributed under its MIT license; see `executor/nova-tracer/LICENSE`.

### Run a Local Skills Directory

For local batches, place each skill in its own subdirectory containing
`SKILL.md`, then queue or execute the directory:

Use the helper menu for the default reproduction path. For local skills
outside the crawled dataset, the helper also provides `queue-skills`,
`exec-queue`, and `exec-dir` subcommands; run `python3 helper.py --help` for
their options. Adding new skills only requires regenerating the queue; the
image does not need to be rebuilt.

## Configuration

Use the helper menu to create `.env` and edit common runtime settings.
Lower-level defaults remain in `config.yaml` for advanced users who need to
tune crawler, scanner, analyzer, or executor internals.

## Environment Variables

| Variable | Description |
|----------|-------------|
| `GITHUB_TOKEN` | GitHub token for repository access |
| `SKILLSMP_API_KEY` | SkillsMP API key for the default crawl path |
| `CLAUDE_CREDENTIALS_FILE` | Local Claude Code credentials file |
| `CC_MODEL`, `CC_JOBS` | Claude Code model and parallel job count for optional triage |
| `CC_RISK_LEVELS` | Static-scan risk buckets sent to CC triage (default `low medium high critical safe`) |
| `SKIP_CRAWL`, `SKIP_REST_CRAWL`, `REQUIRE_CRAWL_ITEMS` | Crawl phase controls; `REQUIRE_CRAWL_ITEMS=true` (default) fails step 1 when no items are collected |
| `DOWNLOAD_LIMIT`, `SCAN_LIMIT`, `RUN_QUEUE_LIMIT`, `CC_QUEUE_LIMIT` | Batch size controls; `RUN_QUEUE_LIMIT` is the per-run execution limit |
| `ENABLE_CC_ANALYSIS` | Run optional Claude Code analysis after dynamic execution |
| `RUN_QUEUE_SOURCE`, `RUN_FROM_RISKS`, `RUN_FROM_CATEGORIES` | Execution queue source and filters |
| `RUN_QUEUE_STATE_FILE`, `RETRY_TIMEOUT_ARTIFACTS` | Execution state file and optional retry of timeout entries that already captured NOVA artifacts |
| `RUN_PROMPT_TEMPLATE` | Dynamic execution prompt template |
| `DOCKER_IMAGE`, `NODE_MAJOR`, `EXEC_WORKERS`, `EXEC_TIMEOUT` | Sandbox image/runtime settings; `EXEC_TIMEOUT` is the inner Claude CLI budget (host bounds the whole `docker run` at `EXEC_TIMEOUT + 180s`) |
| `EXEC_QUIET`, `EXEC_QUIET_THRESHOLD` | `auto`/`true`/`false` (default `auto`); auto goes quiet when pending tasks > threshold (default 10). Quiet mode redirects per-skill subprocess output to `logs/exec/` and prints one status line per skill. |
| `USE_NOVA`, `NOVA_PROFILE`, `NOVA_PROVIDER`, `NOVA_BLOCK` | Runtime NOVA toggles (provider defaults to `tracer`; block defaults to `false`) |
| `NOVA_MODE` | Docker build mode (`none`, `lite`, or `full`); set at image build time, not runtime |
| `STRICT_DOWNLOAD`, `SKIP_EXECUTION`, `ALLOW_EXECUTION_FAILURES` | Failure behavior controls for manual script runs |

## Output

### Static Scan Results
- `workspace/static/critical/` - Critical risk repository reports
- `workspace/static/high/` - High risk repository reports
- `workspace/static/medium/` - Medium risk repository reports
- `workspace/static/low/` - Low risk repository reports
- `workspace/static/safe/` - Safe repository reports

### LLM Triage Results (only when CC analysis runs)
- `scan_results/SAFE/` - LLM triage category
- `scan_results/SUSPICIOUS/` - LLM triage category
- `scan_results/MALICIOUS/` - LLM triage category
- `scan_results/ERROR/` - Failed analyses (invalid JSON, missing status, API errors)
- `scan_results/logs/` - Per-run CC analyzer log files

### Execution Logs
- `workspace/dynamic/{risk_level}/{repo_id}/{skill_name}/{run-id}/`
  - `strace.log` - System call trace
  - `network.pcap` - Network traffic capture
  - `nova-tracer/` - Real Nova-tracer sessions and HTML reports
  - `metadata.json` - Execution metadata
  - `claude_output.txt` - Claude execution output
  - `filesystem_changes.json` - File system changes

### Task Queues
- `tasks/run_queue.txt` - Generated by step 5; full list of dynamic-execution candidates
- `tasks/run_queue_state.jsonl` - Per-task completion state; lets later runs skip done entries
- `tasks/cc_queue.txt` - Generated by step 7 when CC analysis is enabled
- `tasks/local_skills_queue.txt` - Generated by `helper.py queue-skills` / `exec-dir`

### Helper Build Logs
- `logs/docker_build_<timestamp>.log` - Full Docker build output captured by `helper.py build` (concise progress is also printed to the terminal)

## License

MIT License - See [../LICENSE](../LICENSE) for details.

## Contributing

Contributions are welcome! Please submit pull requests or open issues for bugs and feature requests.

For more details about the MaliciousAgentSkillsBench project, see the [main README](../).
