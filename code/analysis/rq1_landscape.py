#!/usr/bin/env python3
"""Generate RQ1 landscape statistics from ``data/malicious_skills.csv``.

Usage:
    python3 rq1_landscape.py
    python3 rq1_landscape.py --csv ../../data/malicious_skills.csv --outdir out/
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from dataset import DEFAULT_CSV, load_skills
from patterns import PHASE_ORDER, TAXONOMY, normalize_pattern


def load_instances(csv_path):
    """Return aligned pattern and severity tokens for each skill."""
    rows = []
    with Path(csv_path).open(newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            codes = [normalize_pattern(p) for p in r["Pattern"].split(";") if p.strip()]
            sev = [s.strip().upper() for s in (r.get("Severity") or "").split(";") if s.strip()]
            rows.append((r["repo"].strip(), r["skill_name"].strip(), codes, sev))
    return rows


def gini(values):
    """Gini coefficient of a list of non-negative values."""
    xs = sorted(values)
    n = len(xs)
    total = sum(xs)
    if n == 0 or total == 0:
        return 0.0
    cum = sum((i + 1) * v for i, v in enumerate(xs))
    return (2 * cum) / (n * total) - (n + 1) / n


def excess_kurtosis(values):
    """Population excess (Fisher) kurtosis."""
    n = len(values)
    m = sum(values) / n
    m2 = sum((v - m) ** 2 for v in values) / n
    m4 = sum((v - m) ** 4 for v in values) / n
    return m4 / (m2 ** 2) - 3 if m2 > 0 else 0.0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", default=str(DEFAULT_CSV), help="path to malicious_skills.csv")
    ap.add_argument("--outdir", default="analysis_output/rq1", help="output directory")
    args = ap.parse_args()

    rows = load_instances(args.csv)
    skills = load_skills(args.csv)
    N = len(rows)
    total = sum(len(c) for _, _, c, _ in rows)

    # Overview and severity distribution
    sev_counter = Counter(s for _, _, _, sev in rows for s in sev)
    codes_present = sorted({c for _, _, cs, _ in rows for c in cs})

    print(f"RQ1 threat landscape  (N={N} skills, {total} vulnerability instances)\n")
    print("[Overview]")
    print(f"  unique patterns present : {len(codes_present)}")
    counts = [len(c) for _, _, c, _ in rows]
    counts_sorted = sorted(counts)
    mean = total / N
    median = counts_sorted[N // 2] if N % 2 else (counts_sorted[N // 2 - 1] + counts_sorted[N // 2]) / 2
    print(f"  mean vulns/skill        : {mean:.2f}")
    print(f"  median vulns/skill      : {median:g}")
    crit_high = sev_counter['CRITICAL'] + sev_counter['HIGH']
    print(f"  severity distribution   : "
          + ", ".join(f"{k} {sev_counter[k]} ({100*sev_counter[k]/total:.1f}%)"
                      for k in ("CRITICAL", "HIGH", "MEDIUM", "LOW")))
    print(f"  CRITICAL+HIGH           : {crit_high} ({100*crit_high/total:.1f}%)")

    # Vulnerability-density distribution
    hist = Counter(counts)
    le2 = sum(1 for c in counts if c <= 2)
    ge3 = sum(1 for c in counts if c >= 3)
    peak = max(hist, key=lambda k: hist[k])
    print("\n[Vulnerability density per skill]")
    print("  histogram (count -> #skills):",
          {k: hist[k] for k in sorted(hist)})
    print(f"  peak at {peak} vulns/skill ({hist[peak]} skills)")
    print(f"  1-2 vulns : {le2} ({100*le2/N:.1f}%)    >=3 vulns : {ge3} ({100*ge3/N:.1f}%)")
    print(f"  excess kurtosis : {excess_kurtosis(counts):+.2f}   Gini : {gini(counts):.3f}")
    print(f"  max vulns in a single skill : {max(counts)}")

    # Per-pattern severity split
    pat_sev = defaultdict(Counter)
    for _, _, cs, sev in rows:
        for c, s in zip(cs, sev):
            pat_sev[c][s] += 1
    print("\n[Per-pattern CRITICAL share (instance level)]")
    for c in sorted(pat_sev, key=lambda c: -sum(pat_sev[c].values())):
        tot = sum(pat_sev[c].values())
        crit = pat_sev[c]['CRITICAL']
        print(f"  {c:4s} n={tot:>3}  CRITICAL {crit:>3} ({100*crit/tot:>5.1f}%)")

    # Instruction-level share
    instr = sum(1 for _, _, cs, _ in rows for c in cs if c in {"P1", "P2", "P3", "P4"})
    print(f"\n[Instruction-level P1-P4]  {instr}/{total} = {100*instr/total:.1f}% of instances")

    # Kill chain phase coverage
    code2phase = {c: TAXONOMY[c].phase for c in TAXONOMY}
    phase_pats = defaultdict(list)
    for c in codes_present:
        if c in TAXONOMY:
            phase_pats[TAXONOMY[c].phase].append(c)
    phase_members = defaultdict(set)
    per_skill_phases = []
    for i, s in enumerate(skills):
        phs = {code2phase[c] for c in s.codes if c in code2phase}
        per_skill_phases.append(len(phs))
        for p in phs:
            phase_members[p].add(i)

    print("\n[Kill chain phase coverage]  (% of {0})".format(N))
    for ph in PHASE_ORDER:
        m = len(phase_members[ph])
        print(f"  {ph:<18} {'/'.join(phase_pats.get(ph, []) or ['-']):<12} "
              f"{m:>4} ({100*m/N:.1f}%)")
    ph_hist = Counter(per_skill_phases)
    ge3p = sum(1 for x in per_skill_phases if x >= 3)
    ge4p = sum(1 for x in per_skill_phases if x >= 4)
    pmean = sum(per_skill_phases) / N
    pmed = sorted(per_skill_phases)[N // 2]
    print("  per-skill phase-count histogram:", {k: ph_hist[k] for k in sorted(ph_hist)})
    print(f"  mean phases/skill {pmean:.2f}  median {pmed}  "
          f">=3 phases {ge3p} ({100*ge3p/N:.1f}%)  >=4 phases {ge4p} ({100*ge4p/N:.1f}%)")

    # Cross-family conditional probabilities
    E = set(i for i, s in enumerate(skills) if s.codes & {"E1", "E2", "E3"})
    SC = set(i for i, s in enumerate(skills) if s.codes & {"SC1", "SC2", "SC3"})
    print("\n[Cross-family conditional probabilities]  (E = E1/E2/E3, SC = SC1/SC2/SC3)")
    print(f"  P(SC | E) = {100*len(E & SC)/len(E):.1f}%    P(E | SC) = {100*len(E & SC)/len(SC):.1f}%")

    # Machine-readable summary
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    summary = {
        "n_skills": N,
        "n_instances": total,
        "unique_patterns_present": len(codes_present),
        "mean_vulns_per_skill": round(mean, 4),
        "median_vulns_per_skill": median,
        "severity_distribution": {k: sev_counter[k] for k in ("CRITICAL", "HIGH", "MEDIUM", "LOW")},
        "crit_high_pct": round(100 * crit_high / total, 2),
        "density_histogram": {int(k): hist[k] for k in sorted(hist)},
        "share_1_2_pct": round(100 * le2 / N, 2),
        "share_ge3_pct": round(100 * ge3 / N, 2),
        "excess_kurtosis": round(excess_kurtosis(counts), 3),
        "gini_per_skill": round(gini(counts), 3),
        "max_vulns_single_skill": max(counts),
        "instruction_level_pct": round(100 * instr / total, 2),
        "phase_membership": {ph: len(phase_members[ph]) for ph in PHASE_ORDER},
        "phase_count_histogram": {int(k): ph_hist[k] for k in sorted(ph_hist)},
        "mean_phases_per_skill": round(pmean, 3),
        "ge3_phases_pct": round(100 * ge3p / N, 2),
        "ge4_phases_pct": round(100 * ge4p / N, 2),
        "P_SC_given_E_pct": round(100 * len(E & SC) / len(E), 2),
        "P_E_given_SC_pct": round(100 * len(E & SC) / len(SC), 2),
        "per_pattern_critical_share": {
            c: {"n": sum(pat_sev[c].values()), "critical": pat_sev[c]["CRITICAL"],
                "critical_pct": round(100 * pat_sev[c]["CRITICAL"] / sum(pat_sev[c].values()), 1)}
            for c in sorted(pat_sev)
        },
    }
    (outdir / "rq1_landscape.json").write_text(json.dumps(summary, indent=2))
    print(f"\nMachine-readable summary -> {outdir/'rq1_landscape.json'}")


if __name__ == "__main__":
    main()
