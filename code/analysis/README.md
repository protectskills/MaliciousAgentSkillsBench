# RQ1/RQ2 Statistical Analysis (Landscape + Taxonomy + Co-occurrence + Hypothesis Tests)

This directory generates the paper's quantitative analysis from
`../../data/malicious_skills.csv` and `../../data/skills_dataset.csv`.

## Two granularities, one data file

`malicious_skills.csv` stores one row per skill. `Pattern` and `Severity` contain
aligned per-instance tokens. Scripts aggregate them at one of two levels:

| Granularity | How | Reproduces |
|---|---|---|
| **Instance-level** | sum tokens, **no dedup** | taxonomy table per-pattern counts → `taxonomy_counts.py` |
| **Skill-level** | dedup each skill's tokens to a `set` | co-occurrence matrix + Fisher / severity → `cooccurrence.py`, `hypothesis_tests.py` |

## Files

| File | Role |
|------|------|
| `patterns.py` | 14-pattern taxonomy (codes, kill-chain phases, severity tiers, MITRE) + display-name → code map. |
| `dataset.py` | Loads `malicious_skills.csv`; normalizes `Pattern` to codes (per-skill `set`) and reads the per-instance `Severity` column. |
| `taxonomy_counts.py` | Instance-level (non-deduped) per-pattern counts → the paper's taxonomy table. |
| `rq1_landscape.py` | RQ1 landscape: overview stats, vulnerability-density distribution (+ kurtosis/Gini), per-pattern severity split, instruction-level share, kill chain phase coverage, cross-family conditionals. |
| `phase_cooccurrence.py` | Kill chain phase co-occurrence matrix (Appendix). |
| `cooccurrence.py` | Skill-level co-occurrence count / conditional-probability / odds-ratio / phi matrices + heatmap. |
| `archetypes.py` | RQ2 archetypes (Data Thieves / Agent Hijackers / hybrid), DT-vs-AH enrichment ORs, hijacker–exfiltration test, E2+E1+P4 triple, smp\_170 share + E2+SC2 fingerprint. |
| `network_analysis.py` | Co-occurrence network: weighted degree (hubs), betweenness, Louvain communities. |
| `hypothesis_tests.py` | Fisher's exact (Bonferroni over the full 14-pattern taxonomy) + Mann-Whitney severity test (per-instance ratings). |
| `dataset_funnel.py` | Per-source funnel (Repos / Snapshot / Candidates / Confirmed) from `skills_dataset.csv`. |
| `requirements.txt` | numpy, scipy, matplotlib, networkx. |

## Quick start

```bash
python3 dataset_funnel.py      # data-sources / funnel table (snapshot CSV)
python3 taxonomy_counts.py     # instance-level taxonomy table
python3 rq1_landscape.py       # RQ1 landscape stats (+ density distribution)
python3 phase_cooccurrence.py  # kill chain phase co-occurrence matrix
python3 cooccurrence.py        # skill-level matrices + heatmap
python3 archetypes.py          # RQ2 archetypes + smp_170 fingerprint
python3 network_analysis.py    # co-occurrence network structure
python3 hypothesis_tests.py    # Fisher / Bonferroni / Mann-Whitney severity
```

`numpy` / `scipy` / `matplotlib` / `networkx` are required.
Outputs default to `code/analysis_output/` (gitignored). Pipeline-style wrappers:
`bash scripts/09_cooccurrence.sh` … `15_funnel.sh`.

## What maps to which paper artifact

| Paper artifact | Reproduced by |
|----------------|---------------|
| Table "Data sources and analysis funnel" (Snapshot/Candidates/Confirmed) | `dataset_funnel.py` |
| Table "Attack technique taxonomy" (per-pattern Count) | `taxonomy_counts.py` (instance-level) |
| Table "Confirmed malicious skills: overview" (mean/median, severity split) | `rq1_landscape.py` |
| Figure "Vulnerability density" (histogram, peak, ≥3 share, kurtosis/Gini) | `rq1_landscape.py` |
| Sentence "SC2: 81.8% CRITICAL, …" (per-pattern severity) | `rq1_landscape.py` |
| Table "Kill chain phase coverage" + Figure "phases per skill" | `rq1_landscape.py` |
| Appendix "Kill chain phase co-occurrence" | `phase_cooccurrence.py` |
| Appendix "Pattern Co-occurrence Matrix" | `cooccurrence.py` → `cooccurrence_counts.csv` |
| Conditional-probability / odds-ratio matrices | `cooccurrence.py` |
| Archetype counts, DT-vs-AH enrichment (E2 OR=23.8, E1 OR=9.7), smp\_170 fingerprint (OR=556) | `archetypes.py` |
| Network hubs / betweenness / Louvain communities | `network_analysis.py` |
| H1: E2↔E1 exfiltration chain (Fisher) | `hypothesis_tests.py` named test `E2~E1` |
| SC2↔P1 anti-correlation → two archetypes | `hypothesis_tests.py` named test `SC2~P1` |
| All-pairs Fisher + Bonferroni (C(14,2) pairs) | `hypothesis_tests.py` `all_pairs` |
| H2: severity ~ prompt injection (Mann-Whitney) | `hypothesis_tests.py` `severity_mannwhitney` (per-instance `Severity`) |

## Data columns & normalization

Columns used here: `Pattern` (semicolon-separated display names, repeated per
instance) and `Severity` (aligned per-instance CRITICAL/HIGH/MEDIUM/LOW rating).
`patterns.py` maps display names to canonical codes.
