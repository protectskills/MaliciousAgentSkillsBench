# "Do Not Mention This to the User": Detecting and Understanding Malicious Agent Skills

![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)

This repository contains a comprehensive security benchmark dataset and evaluation framework for Claude Code Agent Skills. The paper reports a **three-tiered, nested** dataset of __98,380 skills__ from two major platforms (skills.rest and skillsmp.com): **4,287 statically-flagged suspicious candidates** (Tier 2), of which **157 are behaviorally-confirmed malicious skills** (Tier 3). The 157 confirmed skills are a verified **subset of** the 4,287 candidates — not a separate group — and the candidates are themselves a subset of the 98,380-skill snapshot.

## Project Structure

```
MaliciousAgentSkillsBench/
├── data/                           # Benchmark datasets
│   ├── malicious_skills.csv        # 157 malicious skill samples
│   ├── skills_dataset.csv          # Ecosystem snapshot; see Data section
├── code/                           # Security analysis framework
│   ├── helper.py                   # Interactive reproduction CLI (main entry point)
│   ├── analyzer/                   # Optional LLM-assisted triage
│   ├── crawler/                    # Multi-platform data crawler (registry crawler)
│   ├── executor/                   # Dynamic execution in Docker sandbox (behavioral verification harness)
│   ├── scanner/                    # Static rule-based security scanner (static analysis rules)
│   ├── analysis/                   # RQ2 statistics: taxonomy counts + co-occurrence + hypothesis tests
│   │   ├── taxonomy_counts.py      # Instance-level taxonomy counts (632)
│   │   ├── cooccurrence.py         # Co-occurrence matrices + heatmap
│   │   ├── hypothesis_tests.py     # Fisher / Bonferroni / Mann-Whitney severity
│   │   ├── patterns.py             # Pattern taxonomy (codes, phases, severity)
│   │   ├── dataset.py              # Loader for malicious_skills.csv
│   │   └── requirements.txt        # numpy, scipy, matplotlib
│   ├── scripts/                    # Pipeline shell scripts and shared helpers
│   │   ├── run_pipeline.sh         # Scripted step runner
│   │   ├── lib.sh                  # Shared shell functions
│   │   ├── 01_crawl.sh … 08_cc_analyze.sh
│   │   └── 09_cooccurrence.sh, 10_hypothesis.sh  # RQ2 analysis on the released set
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

The dataset is **three-tiered and nested**, matching Table 1 of the paper: every
Tier 3 (confirmed malicious) skill is also a Tier 2 (suspicious candidate), and
every Tier 2 skill is in Tier 1. The 157 confirmed malicious skills are therefore
**included in** the 4,287 suspicious candidates, not counted on top of them.

| Source | Repos | Tier 1 (All) | Tier 2 (Suspicious) | Tier 3 (Malicious) |
|--------|-------|--------------|---------------------|--------------------|
| skills.rest | 2,337 | 25,187 | 814 | 21 |
| skillsmp.com | 8,909 | 73,193 | 3,473 | 136 |
| **Total** | **11,246** | **98,380** | **4,287** | **157** |

Tiers 2 and 3 are **nested** (Tier 3 ⊆ Tier 2 ⊆ Tier 1), so the columns are not
additive. In `skills_dataset.csv` the `classification` column instead uses three
**mutually exclusive** labels, so the released per-label counts are `safe`
(94,093) + `suspicious` (4,130) + `malicious` (157) = 98,380. There, `suspicious`
holds only the **4,130 unconfirmed** candidates (Tier 2 minus Tier 3); adding the
157 `malicious` rows back reconstructs the paper's Tier 2 total: 4,130 + 157 =
4,287.

### Data Files

#### `malicious_skills.csv`
Curated dataset of **157 verified malicious agent skills** from **69 unique repositories**, with detailed vulnerability pattern classifications.

**Columns:**
- `source`: Data source (skills.rest / skillsmp.com)
- `repo`: Repository identifier
- `skill_name`: Name of the malicious skill
- `classification`: Security classification (malicious)
- `Pattern`: Detected vulnerability patterns (semicolon-separated)
- `Severity`: Per-instance severity rating (one CRITICAL / HIGH / MEDIUM / LOW per `Pattern` token)

#### `skills_dataset.csv`
Tier-1 ecosystem snapshot of all **98,380 skills**. The `classification` column carries three mutually exclusive labels — `safe` (94,093), `suspicious` (4,130 unconfirmed candidates), and `malicious` (157 behaviorally confirmed). The paper's Tier 2 (4,287 suspicious candidates) is the **union** of the `suspicious` and `malicious` rows: the 157 confirmed malicious skills are a subset of the 4,287 statically-flagged candidates (4,130 + 157 = 4,287).

**Columns:**
- `source`: Data source (skills.rest / skillsmp.com)
- `repo`: Repository identifier
- `skill_name`: Name of the skill
- `classification`: Security classification — one of `safe`, `suspicious` (statically flagged, not behaviorally confirmed), or `malicious` (behaviorally confirmed). The labels are mutually exclusive; `suspicious` + `malicious` together are the paper's 4,287 Tier-2 candidates.
- `url`: Download URL for the skill repository. Two redaction markers are used to avoid distributing direct download pointers to repositories that host confirmed malicious skills:
    - `[REDACTED]` — the row itself is `classification=malicious`.
    - `[REDACTED:repo_contains_malicious]` — This row shares the same (source, repo) with at least one confirmed malicious skill. The downstream code matching `^\[REDACTED` applies to both.
    
    A small number of skillsmp.com entries with no associated public repository have an empty `url`.

## Code

The `code/` directory contains a reproducible security analysis pipeline for Claude Code Skills.

### Open Science Component Map

The paper's Open Science statement releases the detection pipeline as five named
components. This table maps each component to where it lives in this repository
and the pipeline step that runs it, so the analysis funnel — from a registry-wide
snapshot down to the confirmed set and its statistics — can be navigated and
re-executed component by component.

| Open Science component | Code location | Pipeline step | Reproduces |
|------------------------|---------------|---------------|------------|
| **Registry crawler** | `code/crawler/crawler.py` | `01_crawl.sh` | Registry-wide skill snapshot from skills.rest / skillsmp.com |
| **Static analysis rules** | `code/scanner/scanner.py` + `code/scanner/skill-security-scan/` (`config/rules.yaml`, `src/rules/`) | `04_scan.sh` | Statically-flagged suspicious candidate set |
| **Behavioral verification harness** | `code/executor/` (`run_skill_hostauth.sh`, `batch_runner.py`, `smart_monitor.py`, `nova-tracer/`) | `05_gen_run_queue.sh`, `06_execute.sh` | Sandboxed dynamic confirmation of malicious behavior |
| **Co-occurrence matrices** | `code/analysis/cooccurrence.py` | `09_cooccurrence.sh` | Pattern co-occurrence count/odds-ratio/conditional-probability matrices + heatmap (Section 5.4, Appendix) |
| **Hypothesis-testing scripts** | `code/analysis/hypothesis_tests.py` | `10_hypothesis.sh` | Fisher's exact (E2↔E1, SC2↔P1), Bonferroni, Mann-Whitney severity |

Steps 1–8 are the registry-to-confirmed **funnel** (re-collected against live
registries). Steps 9–10 are **RQ2 statistical analysis** that runs on the
released labeled set (`data/malicious_skills.csv`) and needs no crawl; see
`code/analysis/README.md` for the full artifact-by-artifact mapping and
reproduction-fidelity notes.

### Quick Start

```bash
cd MaliciousAgentSkillsBench/code

# 1. Install dependencies
pip install -r requirements.txt

# 2. Open the interactive helper and follow the menu
python3 helper.py
```

### Prerequisites

Running the live pipeline (steps 1–8) needs two things beyond the Python deps:

- **SkillsMP API key** (default crawl path) — sign up or log in at
  [https://skillsmp.com](https://skillsmp.com) and generate the key from your
  account settings, then set `SKILLSMP_API_KEY` in `code/.env`. It is sent as an
  `Authorization: Bearer` header to the SkillsMP search API.
- **Docker sandbox image** (dynamic execution) — obtain it any of three ways:
  - Pull the prebuilt image: `docker pull ghcr.io/protectskills/claude-skill-sandbox:lite`
  - Or download `claude-skill-sandbox-lite.tar.gz` from the `sandbox-lite-v1`
    GitHub release and import it with `python3 helper.py build --mode load-tar`
    (or `docker load -i claude-skill-sandbox-lite.tar.gz`).
  - Or build locally from `code/Dockerfile`.

  See `code/DOCKER_BUILD.md` for offline import, build modes, and verification,
  and `code/README.md` for the full environment-variable reference.

The RQ2 analysis (steps 9–10) needs neither — it runs on the released
`data/malicious_skills.csv`; see `code/analysis/README.md`.

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
| 9 | `09_cooccurrence.sh` | RQ2 analysis: co-occurrence matrices + heatmap from the released labeled set |
| 10 | `10_hypothesis.sh` | RQ2 analysis: Fisher / Bonferroni / Mann-Whitney severity hypothesis tests |

Steps 1–8 form the registry-to-confirmed funnel and run in sequence via
`scripts/run_pipeline.sh`. Steps 9–10 are standalone post-labeling analysis on
`data/malicious_skills.csv` and are run directly (they are not part of
`run_pipeline.sh`). See `code/analysis/README.md`.

### Key Components

**Helper (`helper.py`)**
- Interactive CLI that wraps the pipeline scripts; the recommended entry point. Run `python3 helper.py` and use the menu to initialize configuration, check the environment, build the sandbox image, run the default small-batch experiment, view status, and clean runtime outputs.

**Analyzer (`analyzer/`)**
- `cc_analyzer.sh`: Claude Code integration for optional LLM-assisted triage
- `prompts/audit_prompt.txt`: Security audit prompt template

**Scanner (`scanner/`)**
- `scanner.py`: Rule-based static security scanner
- Uses skill-security-scan tool for vulnerability detection

**Executor (`executor/`)** — behavioral verification harness
- `run_skill_hostauth.sh`: Docker sandbox execution with local Claude login (default)
- `run_skill.sh`: Legacy API-token Docker executor
- `batch_runner.py`: Concurrent execution manager
- `smart_monitor.py`: File system and network monitoring
- `nova_setup.sh`: Nova-tracer hook setup

**Analysis (`analysis/`)** — taxonomy counts, co-occurrence matrices, and hypothesis-testing scripts. Two granularities come from one `malicious_skills.csv`: summing `Pattern` tokens without dedup gives instance-level counts; deduping per skill gives the skill-level matrices/tests.
- `taxonomy_counts.py`: instance-level (non-deduped) per-pattern counts → the paper's attack-technique taxonomy table (632)
- `cooccurrence.py`: builds the pattern co-occurrence count/odds-ratio/conditional-probability/phi matrices and renders the co-occurrence heatmap (paper Section 5.4 and Appendix)
- `hypothesis_tests.py`: Fisher's exact tests with Bonferroni correction and Mann-Whitney U severity test
- `patterns.py` / `dataset.py`: pattern taxonomy and loader for `data/malicious_skills.csv`
- `requirements.txt`: numpy, scipy, matplotlib
- Run via `scripts/09_cooccurrence.sh` and `scripts/10_hypothesis.sh`, or `python3 taxonomy_counts.py`. See `analysis/README.md`.

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

analysis_output/                    # RQ2 analysis outputs (steps 9-10)
├── cooccurrence/                   # Matrices (CSV) + pattern_cooccurrence.pdf/.png
└── hypothesis/                     # hypothesis_tests.json
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
@misc{MaliciousAgentSkillsBench,
      title={"Do Not Mention This to the User": Detecting and Understanding Malicious Agent Skills in the Wild}, 
      author={Yi Liu and Zhihao Chen and Yanjun Zhang and Gelei Deng and Yuekang Li and Jianting Ning and Leo Yu Zhang},
      year={2026},
      eprint={2602.06547},
      archivePrefix={arXiv},
      primaryClass={cs.CR},
      url={https://arxiv.org/abs/2602.06547}, 
}
```

## License

`MaliciousAgentSkillsBench` is licensed under the MIT License. See LICENSE for more details.
