# "Do Not Mention This to the User": Detecting and Understanding Malicious Agent Skills

![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)

This repository contains a comprehensive security benchmark dataset and evaluation framework for Claude Code Agent Skills. The paper reports __98,380 skills__ from two major platforms (skills.rest and skillsmp.com), including **4,287 statically-flagged suspicious candidates** and **157 behaviorally-confirmed malicious skills**.

## Project Structure

```
MaliciousAgentSkillsBench/
├── data/                           # Benchmark datasets
│   ├── malicious_skills.csv        # 157 malicious skill samples
│   ├── skills_dataset.csv          # Ecosystem snapshot; see Data section
├── code/                           # Security analysis framework
│   ├── helper.py                   # Interactive reproduction CLI (main entry point)
│   ├── analyzer/                   # Optional LLM-assisted triage
│   ├── crawler/                    # Multi-platform data crawler
│   ├── executor/                   # Dynamic execution in Docker sandbox
│   ├── scanner/                    # Static rule-based security scanner
│   ├── scripts/                    # Pipeline shell scripts and shared helpers
│   │   ├── run_pipeline.sh         # Scripted step runner
│   │   ├── lib.sh                  # Shared shell functions
│   │   └── 01_crawl.sh … 08_cc_analyze.sh
│   ├── Dockerfile                  # Sandbox image definition
│   ├── config.yaml                 # Path and pipeline configuration
│   └── .env.example                # Environment template
└── README.md                       # This file
```

## Disclaimer

__This repository contains examples of malicious agent skills for research purposes only. Reader discretion is recommended. Any misuse is strictly prohibited.__

The code and data in this repository are intended exclusively for:
- Academic research on AI agent security
- Developing defense mechanisms against malicious agent skills
- Evaluating the robustness of AI agent platforms

## Data

### Dataset Statistics

| Source | Repos | Total Skills | Suspicious | Malicious |
|--------|-------|--------------|------------|-----------|
| skills.rest | 3,217 | 25,187 | 814 | 21 |
| skillsmp.com | 10,373 | 73,193 | 3,473 | 136 |
| **Total** | **13,590** | **98,380** | **4,287** | **157** |

### Data Files

#### `malicious_skills.csv`
Curated dataset of **157 verified malicious agent skills** from **69 unique repositories**, with detailed vulnerability pattern classifications.

**Columns:**
- `source`: Data source (skills.rest / skillsmp.com)
- `repo`: Repository identifier
- `skill_name`: Name of the malicious skill
- `classification`: Security classification (malicious)
- `Pattern`: Detected vulnerability patterns (semicolon-separated)

#### `skills_dataset.csv`
Tier-1 ecosystem snapshot of **98,380 skills** with security classifications (4,287 suspicious, 157 malicious).

**Columns:**
- `source`: Data source (skills.rest / skillsmp.com)
- `repo`: Repository identifier
- `skill_name`: Name of the skill
- `classification`: Security classification (safe / suspicious / malicious)
- `url`: Download URL for the skill repository. Two redaction markers are used to avoid distributing direct download pointers to repositories that host confirmed malicious skills:
    - `[REDACTED]` — the row itself is `classification=malicious`.
    - `[REDACTED:repo_contains_malicious]` — This row shares the same (source, repo) with at least one confirmed malicious skill. The downstream code matching `^\[REDACTED` applies to both.
    
    A small number of skillsmp.com entries with no associated public repository have an empty `url`.

## Code

The `code/` directory contains a reproducible security analysis pipeline for Claude Code Skills.

### Quick Start

```bash
cd MaliciousAgentSkillsBench/code

# 1. Install dependencies
pip install -r requirements.txt

# 2. Open the interactive helper and follow the menu
python3 helper.py
```

### Small-Batch Reproduction

The default configuration runs a small-batch experiment through dynamic
execution. Increase the crawl, download, scan, queue, and worker limits in
`code/.env` for larger runs.

This path uses SkillsMP, maps repositories, downloads and scans them, generates
an execution queue from static scan reports, and dynamically executes selected
skills in the Docker sandbox. Optional Claude Code triage can be enabled after
dynamic execution. Runtime outputs are written under gitignored directories in
`code/`.

Warning: dynamic execution is instrumentation, not a strong isolation boundary.
The default host-auth executor mounts a Claude Code credential into a Docker
container and runs Claude with skipped permissions. Use a disposable Claude
login and a disposable VM/host for untrusted skills.

The paper's ground-truth labels are produced by static candidate detection,
sandboxed behavioral verification, and independent human review. The optional
Claude Code analysis step in this reproduction is a post-hoc automation aid,
not the final labeling oracle.

Note: `skills.rest` currently returns a Cloudflare managed challenge from
headless/server requests, and no public API specification or authentication
flow is available for reproducible crawling. The default configuration therefore
uses SkillsMP with `SKIP_REST_CRAWL=true`.


### Pipeline Overview

| Step | Script | Description |
|------|--------|-------------|
| 1 | `01_crawl.sh` | Crawl skill metadata; defaults to SkillsMP and can also use skills.rest when accessible |
| 2 | `02_generate_mapping.sh` | Generate repository mapping |
| 3 | `03_download.sh` | Download skill repositories from GitHub |
| 4 | `04_scan.sh` | Static rule-based security scanning |
| 5 | `05_gen_run_queue.sh` | Generate dynamic execution queue from static scan reports |
| 6 | `06_execute.sh` | Execute skills in Docker sandbox with monitoring |
| 7 | `07_gen_cc_queue.sh` | Optional: generate Claude Code triage queue |
| 8 | `08_cc_analyze.sh` | Optional: run LLM-assisted triage |

### Key Components

**Helper (`helper.py`)**
- Interactive CLI that wraps the pipeline scripts; the recommended entry point. Run `python3 helper.py` and use the menu to initialize configuration, check the environment, build the sandbox image, run the default small-batch experiment, view status, and clean runtime outputs.

**Analyzer (`analyzer/`)**
- `cc_analyzer.sh`: Claude Code integration for optional LLM-assisted triage
- `prompts/audit_prompt.txt`: Security audit prompt template

**Scanner (`scanner/`)**
- `scanner.py`: Rule-based static security scanner
- Uses skill-security-scan tool for vulnerability detection

**Executor (`executor/`)**
- `run_skill_hostauth.sh`: Docker sandbox execution with local Claude login (default)
- `run_skill.sh`: Legacy API-token Docker executor
- `batch_runner.py`: Concurrent execution manager
- `smart_monitor.py`: File system and network monitoring
- `nova_setup.sh`: Nova-tracer hook setup

### Output Structure

```
scan_results/                       # Only when optional CC analysis runs
├── SAFE/                           # LLM triage category
├── SUSPICIOUS/                     # LLM triage category
├── MALICIOUS/                      # LLM triage category
├── ERROR/                          # Failed analyses (invalid JSON, missing status, API errors)
└── logs/                           # Per-run CC analyzer logs

workspace/dynamic/                  # Dynamic execution evidence
├── critical/{repo_id}/{skill_name}/{run-id}/
│   ├── strace.log                  # System call trace
│   ├── network.pcap                # Network traffic capture
│   ├── nova-tracer/                # Nova-tracer sessions and HTML reports
│   ├── metadata.json               # Execution metadata
│   ├── claude_output.txt           # Claude execution output
│   └── filesystem_changes.json     # File system modifications
├── high/...
├── medium/...
├── low/...
└── safe/...

tasks/                              # Pipeline state and queues
├── run_queue.txt                   # Generated by step 5; full execution candidate list
├── run_queue_state.jsonl           # Per-task completion state for resumable runs
└── cc_queue.txt                    # Generated by step 7 when CC analysis is enabled
```

NOVA reports, Claude outputs, packet captures, and filesystem traces are
sensitive experiment artifacts. Review and redact them before sharing.

## Ethics

We acknowledge that security research on AI agents requires access to potentially harmful examples. This study follows ethical best practices:

1. **Research Purpose Only**: This dataset is exclusively for defensive security research
2. **No Live Attacks**: Dynamic analysis is intended for monitored, disposable sandbox environments and is not a strong isolation guarantee
3. **Responsible Disclosure**: Vulnerabilities are reported to platform vendors
4. **Aggregate Reporting**: Results are reported in aggregate, not targeting specific developers

The goal of this work is to raise awareness of AI agent security risks and inform the development of stronger safeguards.

## Third-Party Components

The dynamic execution sandbox vendors a runtime subset of Nova-tracer under
`code/executor/nova-tracer`. Nova-tracer is MIT licensed; its license is
included at `code/executor/nova-tracer/LICENSE`.

## Citation

```bibtex
@misc{malicious_agent_skills_bench,
  title={“Do Not Mention This to the User”: Detecting and Understanding Malicious Agent Skills},
  author={Anonymous},
  year={2026},
}
```

## License

`MaliciousAgentSkillsBench` is licensed under the MIT License. See LICENSE for more details.
