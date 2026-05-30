# RQ2 Statistical Analysis (Taxonomy + Co-occurrence + Hypothesis Tests)

This directory re-derives the paper's RQ2 results (Section 5.4 and the
"Statistical Analysis Details" appendix) directly from the released labeled set
`../../data/malicious_skills.csv` (157 confirmed malicious skills). It needs no
crawl, download, or sandbox — unlike the funnel pipeline
(`scripts/01_crawl.sh` … `08_cc_analyze.sh`).

## Two granularities, one data file

`malicious_skills.csv` keeps one row per skill, but its `Pattern` column repeats
a token once per labeled **vulnerability instance**, with an aligned `Severity`
column (one CRITICAL/HIGH/MEDIUM/LOW rating per token). The paper reports two
granularities, and each script reads the file at the right one:

| Granularity | How | Reproduces |
|---|---|---|
| **Instance-level** | sum tokens, **no dedup** | taxonomy table per-pattern counts → `taxonomy_counts.py` |
| **Skill-level** | dedup each skill's tokens to a `set` | co-occurrence matrix + Fisher / severity → `cooccurrence.py`, `hypothesis_tests.py` |

The same pattern legitimately sums to one value across instances and a smaller
one across skills — both appear in the paper (e.g. the taxonomy Count column vs.
the co-occurrence diagonal). **Do not remove the `set()` dedup** in
`cooccurrence.py` / `hypothesis_tests.py`: those analyses are skill-level by
definition, and counting instances there would inflate the matrix.

## Files

| File | Role |
|------|------|
| `patterns.py` | 14-pattern taxonomy (codes, kill-chain phases, severity tiers, MITRE) + display-name → code map. |
| `dataset.py` | Loads `malicious_skills.csv`; normalizes `Pattern` to codes (per-skill `set`) and reads the per-instance `Severity` column. |
| `taxonomy_counts.py` | Instance-level (non-deduped) per-pattern counts → the paper's taxonomy table. |
| `cooccurrence.py` | Skill-level co-occurrence count / conditional-probability / odds-ratio / phi matrices + heatmap. |
| `hypothesis_tests.py` | Fisher's exact (Bonferroni over the full 14-pattern taxonomy) + Mann-Whitney severity test (per-instance ratings). |
| `requirements.txt` | numpy, scipy, matplotlib. |

## Quick start

```bash
python3 taxonomy_counts.py     # instance-level taxonomy table
python3 cooccurrence.py        # skill-level matrices + heatmap
python3 hypothesis_tests.py    # Fisher / Bonferroni / Mann-Whitney severity
```

`numpy` / `scipy` / `matplotlib` are required.
Outputs default to `code/analysis_output/` (gitignored). Pipeline-style wrappers:
`bash scripts/09_cooccurrence.sh`, `bash scripts/10_hypothesis.sh`.

## What maps to which paper artifact

| Paper artifact | Reproduced by |
|----------------|---------------|
| Table "Attack technique taxonomy" (per-pattern Count) | `taxonomy_counts.py` (instance-level) |
| Appendix "Pattern Co-occurrence Matrix" | `cooccurrence.py` → `cooccurrence_counts.csv` |
| Conditional-probability / odds-ratio matrices | `cooccurrence.py` |
| H1: E2↔E1 exfiltration chain (Fisher) | `hypothesis_tests.py` named test `E2~E1` |
| SC2↔P1 anti-correlation → two archetypes | `hypothesis_tests.py` named test `SC2~P1` |
| All-pairs Fisher + Bonferroni (C(14,2) pairs) | `hypothesis_tests.py` `all_pairs` |
| H2: severity ~ prompt injection (Mann-Whitney) | `hypothesis_tests.py` `severity_mannwhitney` (per-instance `Severity`) |

## Data columns & normalization

Columns used here: `Pattern` (semicolon-separated display names, repeated per
instance) and `Severity` (aligned per-instance CRITICAL/HIGH/MEDIUM/LOW rating).
`patterns.py` maps display names to canonical codes; two notes:

* `Context Leakage` and `Data Exfiltration` both fold into **P3**.
* **E4** (Network Reconnaissance) has zero confirmed instances, per the paper.

Because registries evolve, exact counts shift as the dataset is re-collected; the
scripts operate on whatever patterns are present in the input rather than
assuming a fixed set.
