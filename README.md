# "Do Not Mention This to the User": Detecting and Understanding Malicious Agent Skills

![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)

This repository contains a comprehensive security benchmark dataset and evaluation framework for Claude Code Agent Skills. We collect __98,380 skills__ from two major platforms (skills.rest and skillsmp.com), including **157 malicious samples** identified through systematic security analysis.

## Project Structure

```
MaliciousAgentSkillsBench/
├── data/                           # Benchmark datasets
│   ├── malicious_skills.csv        # 157 malicious skill samples (curated)
│   ├── skills_dataset.csv          # 98,380 total skills (157 malicious flagged)
├── code/                           # Security analysis framework
│   ├── analyzer/                   # AI-powered deep security analysis
│   ├── crawler/                    # Multi-platform data crawler
│   ├── executor/                   # Dynamic execution in Docker sandbox
│   ├── scanner/                    # Static rule-based security scanner
│   └── scripts/                    # analysis pipeline
│   └── ···                         # other files
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

| Source | Repos | Total Skills | Suspicious |Malicious |
|--------|-------|--------------|-----------|------|
| skills.rest | 3,217 | 25,187 |814|  21  |
| skillsmp.com | 10,373 | 73,193 | 3,473 | 136 |
| **Total** | **13,590**| **98,380** | **4,287** | **157** |

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
Complete dataset of **98,380 skills** with security classifications (157 flagged as malicious).

**Columns:**
- `source`: Data source (skills.rest / skillsmp.com)
- `repo`: Repository identifier
- `skill_name`: Name of the skill
- `classification`: Security classification (safe / suspicious / malicious)
- `url`: Download URL for the skill repository

### Load Dataset

```python
import pandas as pd

# Load malicious skills only
malicious_df = pd.read_csv('data/malicious_skills.csv')
print(f"Malicious skills: {len(malicious_df)}")

# Load complete dataset
full_df = pd.read_csv('data/skills_dataset.csv')
print(f"Total skills: {len(full_df)}")
print(f"Class distribution:\n{full_df['classification'].value_counts()}")
```

## Code

The `code/` directory contains a complete security analysis pipeline for Claude Code Skills.

## Known Setup Issues

Some setup issues were encountered during local deployment on Linux (import errors, Docker dependency mirror issue, and missing `skill-security-scan` component).

See `SETUP_FIXES.md` for the commands and modifications used to resolve them.
### Quick Start

```bash
cd MaliciousAgentSkillsBench/code

# 1. Install dependencies
pip install -r requirements.txt

# 2. Build Docker sandbox for dynamic execution
docker build -t claude-skill-sandbox -f Dockerfile .

# 3. Configure environment
cp .env.example .env
# Edit .env with your API keys (GITHUB_TOKEN, ANTHROPIC_API_KEY)

# 4. Run complete pipeline
./scripts/run_pipeline.sh

# Or run from a specific step
./scripts/run_pipeline.sh "Static Scan"
```

### Pipeline Overview

| Step | Script | Description |
|------|--------|-------------|
| 1 | `01_crawl.sh` | Crawl skill metadata from skills.rest and skillsmp.com |
| 2 | `02_generate_mapping.sh` | Generate repository mapping |
| 3 | `03_download.sh` | Download skill repositories from GitHub |
| 4 | `04_scan.sh` | Static rule-based security scanning |
| 5 | `05_gen_cc_queue.sh` | Generate Claude Code analysis queue |
| 6 | `06_cc_analyze.sh` | AI-powered deep security audit |
| 7 | `07_gen_run_queue.sh` | Generate dynamic execution queue |
| 8 | `08_execute.sh` | Execute skills in Docker sandbox with monitoring |

### Key Components

**Analyzer (`analyzer/`)**
- `cc_analyzer.sh`: Claude Code integration for AI-powered security analysis
- `prompts/audit_prompt.txt`: Security audit prompt template

**Scanner (`scanner/`)**
- `scanner.py`: Rule-based static security scanner
- Uses skill-security-scan tool for vulnerability detection

**Executor (`executor/`)**
- `run_skill.sh`: Docker sandbox execution script
- `batch_runner.py`: Concurrent execution manager
- `smart_monitor.py`: File system and network monitoring
- `nova_setup.sh`: NOVA hook setup for system call tracing

### Output Structure

```
scan_results/
├── SAFE/           # Skills verified safe
├── SUSPICIOUS/     # Skills with suspicious patterns
└── MALICIOUS/      # Skills with confirmed vulnerabilities

execution_logs/
├── critical/{repo_id}/{skill_name}/
│   ├── strace.log              # System call trace
│   ├── network.pcap            # Network traffic capture
│   ├── nova/                   # NOVA hook reports
│   ├── claude_output.txt       # Claude execution output
│   └── filesystem_changes.json # File system modifications
├── high/...
├── medium/...
└── low/...
```

### Configuration

Edit `config.yaml` to customize:

```yaml
# Crawler settings
crawler:
  skills_rest:
    limit: 60
    max_limit: 300000

# Scanner thresholds
scanner:
  thresholds:
    critical: 8
    high: 6
    medium: 4
    low: 2

# Analyzer settings
analyzer:
  jobs: 10
  max_retries: 3

# Executor settings
executor:
  docker_image: "claude-skill-sandbox"
  max_workers: 3
  timeout: 900
```

## Ethics

We acknowledge that security research on AI agents requires access to potentially harmful examples. This study follows ethical best practices:

1. **Research Purpose Only**: This dataset is exclusively for defensive security research
2. **No Live Attacks**: All analysis is conducted in isolated sandbox environments
3. **Responsible Disclosure**: Vulnerabilities are reported to platform vendors
4. **Aggregate Reporting**: Results are reported in aggregate, not targeting specific developers

The goal of this work is to raise awareness of AI agent security risks and inform the development of stronger safeguards.

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

