#!/usr/bin/env python3
"""Generate attacker-archetype statistics from ``data/malicious_skills.csv``.

Usage:
    python3 archetypes.py
    python3 archetypes.py --csv ../../data/malicious_skills.csv --outdir out/
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scipy.stats import fisher_exact

from dataset import DEFAULT_CSV, load_skills


def fisher(table):
    """Run Fisher's exact test, returning (odds_ratio, p_value) as plain floats."""
    res = fisher_exact(table)
    return float(res[0]), float(res[1])


def odds_ratio_between(group_a, group_b, members):
    """OR of pattern membership between two disjoint skill groups."""
    a = len(group_a & members)
    b = len(group_a - members)
    c = len(group_b & members)
    d = len(group_b - members)
    if b * c == 0:
        return float("inf") if a * d else float("nan"), (a, b, c, d)
    return (a * d) / (b * c), (a, b, c, d)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", default=str(DEFAULT_CSV), help="path to malicious_skills.csv")
    ap.add_argument("--outdir", default="analysis_output/archetypes", help="output directory")
    args = ap.parse_args()

    skills = load_skills(args.csv)
    N = len(skills)
    idx = lambda code: set(i for i, s in enumerate(skills) if code in s.codes)

    SC2, P1 = idx("SC2"), idx("P1")
    data_thieves = SC2 - P1
    hijackers = P1 - SC2
    hybrid = SC2 & P1

    print(f"Loaded {N} confirmed malicious skills.\n")
    print("[Archetypes]")
    print(f"  Data Thieves   (SC2 without P1): {len(data_thieves)} ({100*len(data_thieves)/N:.1f}%)")
    print(f"  Agent Hijackers (P1 without SC2): {len(hijackers)} ({100*len(hijackers)/N:.1f}%)")
    print(f"  Hybrid          (SC2 and P1)    : {len(hybrid)} ({100*len(hybrid)/N:.1f}%)")

    print("\n[Data-Thieves vs Agent-Hijackers enrichment (odds ratio)]")
    enrich = {}
    for code in ("E2", "E1", "SC3"):
        orr, tab = odds_ratio_between(data_thieves, hijackers, idx(code))
        enrich[code] = orr
        print(f"  {code}: OR={orr:.2f}  (a,b,c,d)={tab}")

    exfil = idx("E1") | idx("P3")
    a = len(hijackers & exfil); b = len(hijackers - exfil)
    c = len(exfil - hijackers); d = N - a - b - c
    orr, p = fisher([[a, b], [c, d]])
    print(f"\n[Agent Hijackers vs exfiltration (E1 or P3)]  OR={orr:.3f}  Fisher p={p:.3f}  (a,b,c,d)=({a},{b},{c},{d})")

    triple = set(i for i, s in enumerate(skills) if {"E2", "E1", "P4"} <= s.codes)
    print(f"\n[E2+E1+P4 triple]  {len(triple)} ({100*len(triple)/N:.1f}%)")

    smp170 = set(i for i, s in enumerate(skills) if s.repo == "smp_170")
    e2sc2 = SC2 & idx("E2")
    in_fp = len(smp170 & e2sc2)
    out_total = N - len(smp170)
    out_fp = len(e2sc2 - smp170)
    a = in_fp; b = len(smp170) - in_fp; c = out_fp; d = out_total - out_fp
    orr_fp, p_fp = fisher([[a, b], [c, d]])
    print("\n[smp_170 factory]")
    print(f"  share of confirmed set : {len(smp170)}/{N} = {100*len(smp170)/N:.1f}%")
    print(f"  E2+SC2 in smp_170      : {in_fp}/{len(smp170)} ({100*in_fp/len(smp170):.1f}%)")
    print(f"  E2+SC2 in non-smp_170  : {out_fp}/{out_total} ({100*out_fp/out_total:.1f}%)")
    print(f"  Fisher  OR={orr_fp:.1f}  p={p_fp:.2e}")

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    summary = {
        "n_skills": N,
        "data_thieves": {"n": len(data_thieves), "pct": round(100 * len(data_thieves) / N, 1)},
        "agent_hijackers": {"n": len(hijackers), "pct": round(100 * len(hijackers) / N, 1)},
        "hybrid": {"n": len(hybrid), "pct": round(100 * len(hybrid) / N, 1)},
        "enrichment_or_dt_vs_ah": {k: (None if v != v else (None if v == float("inf") else round(v, 2)))
                                   for k, v in enrich.items()},
        "hijacker_vs_exfiltration": {"odds_ratio": round(orr, 3), "fisher_p": round(p, 4)},
        "triple_E2_E1_P4": {"n": len(triple), "pct": round(100 * len(triple) / N, 1)},
        "smp170": {
            "n": len(smp170), "share_pct": round(100 * len(smp170) / N, 1),
            "fingerprint_in_pct": round(100 * in_fp / len(smp170), 1),
            "fingerprint_out_pct": round(100 * out_fp / out_total, 1),
            "odds_ratio": round(orr_fp, 1), "fisher_p": p_fp,
        },
    }
    (outdir / "archetypes.json").write_text(json.dumps(summary, indent=2))
    print(f"\nMachine-readable summary -> {outdir/'archetypes.json'}")


if __name__ == "__main__":
    main()
