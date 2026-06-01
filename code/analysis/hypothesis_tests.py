#!/usr/bin/env python3
"""Run the RQ2 Fisher and Mann-Whitney hypothesis tests.

Usage:
    python3 hypothesis_tests.py
    python3 hypothesis_tests.py --alpha 0.05 --canonical-only
"""

from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

import numpy as np
from scipy.stats import fisher_exact, mannwhitneyu
from scipy.stats.contingency import odds_ratio as conditional_odds_ratio

from dataset import DEFAULT_CSV, load_skills, present_codes
from patterns import TAXONOMY


def contingency(skills, a, b):
    """2x2 table for patterns a, b: [[both, a_only],[b_only, neither]]."""
    both = a_only = b_only = neither = 0
    for s in skills:
        has_a, has_b = a in s.codes, b in s.codes
        if has_a and has_b:
            both += 1
        elif has_a:
            a_only += 1
        elif has_b:
            b_only += 1
        else:
            neither += 1
    return both, a_only, b_only, neither


def phi_coefficient(both, a_only, b_only, neither):
    import math
    n1_ = both + a_only
    n0_ = b_only + neither
    n_1 = both + b_only
    n_0 = a_only + neither
    denom = math.sqrt(n1_ * n0_ * n_1 * n_0)
    if denom == 0:
        return 0.0
    return (both * neither - a_only * b_only) / denom


def pair_test(skills, a, b):
    """Run a two-sided Fisher's exact test on the (a, b) 2x2 table.

    Table orientation for fisher/odds_ratio: [[both, a_only], [b_only, neither]]
    so OR > 1 means positive association, OR < 1 anti-association.
    """
    both, a_only, b_only, neither = contingency(skills, a, b)
    table = [[both, a_only], [b_only, neither]]
    _, p = fisher_exact(table, alternative="two-sided")
    # Conditional MLE odds ratio with exact confidence interval.
    try:
        res = conditional_odds_ratio(table, kind="conditional")
        orr = float(res.statistic)
        ci = res.confidence_interval(confidence_level=0.95)
        ci_lo, ci_hi = float(ci.low), float(ci.high)
    except Exception:
        orr, ci_lo, ci_hi = float("nan"), float("nan"), float("nan")
    phi = phi_coefficient(both, a_only, b_only, neither)
    return {
        "a": a, "b": b,
        "both": both, "a_only": a_only, "b_only": b_only, "neither": neither,
        "p_value": float(p),
        "odds_ratio": orr,
        "ci95": [ci_lo, ci_hi],
        "phi": phi,
    }


def count(skills, code):
    return sum(1 for s in skills if code in s.codes)


def co(skills, a, b):
    return sum(1 for s in skills if a in s.codes and b in s.codes)


def proportion_ci(k, n, z=1.96):
    """Return a Wald 95% confidence interval in percent."""
    import math
    p = k / n
    half = z * math.sqrt(p * (1 - p) / n)
    return 100 * p, 100 * (p - half), 100 * (p + half)


def lift(skills, a, b):
    n = len(skills)
    pa, pb = count(skills, a) / n, count(skills, b) / n
    return (co(skills, a, b) / n) / (pa * pb) if pa and pb else float("nan")


def banner(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def report_pair(label, r, alpha):
    verdict = "SIGNIFICANT" if r["p_value"] < alpha else "n.s."
    direction = "positive" if r["odds_ratio"] >= 1 else "negative/anti"
    print(f"{label}: {r['a']} <-> {r['b']}")
    print(f"  contingency: both={r['both']}  {r['a']}-only={r['a_only']}  "
          f"{r['b']}-only={r['b_only']}  neither={r['neither']}")
    print(f"  OR={r['odds_ratio']:.3f}  95% CI [{r['ci95'][0]:.2f}, {r['ci95'][1]:.2f}]  "
          f"phi={r['phi']:+.3f}  ({direction})")
    print(f"  Fisher exact two-sided p={r['p_value']:.4g}  ->  {verdict} at alpha={alpha}")


def severity_test(skills, alpha):
    """H2: Mann-Whitney U on severity, prompt-injection (P1 or P2) vs. not."""
    with_pi = [s.severity_score() for s in skills if ("P1" in s.codes or "P2" in s.codes)]
    without_pi = [s.severity_score() for s in skills if not ("P1" in s.codes or "P2" in s.codes)]
    u, p = mannwhitneyu(with_pi, without_pi, alternative="two-sided")
    out = {
        "n_with_pi": len(with_pi),
        "n_without_pi": len(without_pi),
        "mean_with_pi": float(np.mean(with_pi)) if with_pi else float("nan"),
        "mean_without_pi": float(np.mean(without_pi)) if without_pi else float("nan"),
        "U": float(u),
        "p_value": float(p),
    }
    verdict = "SIGNIFICANT" if p < alpha else "n.s."
    print("H2: Severity ~ prompt injection (P1 or P2), Mann-Whitney U")
    print(f"  with PI:    n={out['n_with_pi']:3d}  mean severity={out['mean_with_pi']:.2f}")
    print(f"  without PI: n={out['n_without_pi']:3d}  mean severity={out['mean_without_pi']:.2f}")
    print(f"  U={out['U']:.1f}  p={out['p_value']:.4g}  ->  {verdict} at alpha={alpha}")
    print("  (skill severity = mean of its per-instance Severity ratings)")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", default=str(DEFAULT_CSV), help="path to malicious_skills.csv")
    ap.add_argument("--outdir", default="analysis_output/hypothesis", help="output directory")
    ap.add_argument("--alpha", type=float, default=0.05, help="significance level (default 0.05)")
    ap.add_argument("--canonical-only", action="store_true",
                    help="restrict to the 14-pattern taxonomy")
    args = ap.parse_args()

    skills = load_skills(args.csv, canonical_only=args.canonical_only)
    codes = present_codes(skills, canonical_only=args.canonical_only)
    print(f"Loaded {len(skills)} confirmed malicious skills; patterns present: {', '.join(codes)}")

    results: dict = {"n_skills": len(skills), "alpha": args.alpha, "pairwise": {}}

    banner("Named hypotheses")
    named = [
        ("H1 (Data Thieves exfil chain)", "E2", "E1"),
        ("AC (Data Thieves vs Agent Hijackers anti-correlation)", "SC2", "P1"),
        ("EV (hijacker evasion association)", "P2", "SC3"),
    ]
    for label, a, b in named:
        if a in codes and b in codes:
            r = pair_test(skills, a, b)
            report_pair(label, r, args.alpha)
            results["pairwise"][f"{a}~{b}"] = r
            print()
        else:
            print(f"{label}: {a} or {b} absent in this dataset -> skipped\n")

    banner("Attack archetypes")
    n = len(skills)
    dt = sum(1 for s in skills if "SC2" in s.codes and "P1" not in s.codes)
    ah = sum(1 for s in skills if "P1" in s.codes and "SC2" not in s.codes)
    print(f"Data Thieves   (SC2 without P1): {dt} skills ({100*dt/n:.1f}%)")
    print(f"Agent Hijackers (P1 without SC2): {ah} skills ({100*ah/n:.1f}%)")
    if "E2" in codes and "E1" in codes:
        both = co(skills, "E2", "E1")
        prop, lo, hi = proportion_ci(both, n)
        print(f"E2 & E1 co-occur: {both}/{n} = {prop:.1f}% (95% CI [{lo:.1f}%, {hi:.1f}%])")
    results["archetypes"] = {"data_thieves": dt, "agent_hijackers": ah}

    banner("All-pairs Fisher's exact tests with Bonferroni correction")
    pair_codes = list(TAXONOMY)
    pairs = list(itertools.combinations(pair_codes, 2))
    k = len(pairs)
    bonf = args.alpha / k if k else args.alpha
    print(f"{k} pattern pairs; Bonferroni alpha = {args.alpha}/{k} = {bonf:.2e}\n")
    all_pairs = []
    for a, b in pairs:
        r = pair_test(skills, a, b)
        r["significant_raw"] = r["p_value"] < args.alpha
        r["significant_bonferroni"] = r["p_value"] < bonf
        all_pairs.append(r)
    all_pairs.sort(key=lambda r: r["p_value"])
    print(f"{'pair':12s} {'both':>5s} {'OR':>8s} {'phi':>7s} {'p':>10s}  Bonf")
    for r in all_pairs:
        flag = "***" if r["significant_bonferroni"] else ("*" if r["significant_raw"] else "")
        print(f"{r['a']+'~'+r['b']:12s} {r['both']:5d} {r['odds_ratio']:8.3f} "
              f"{r['phi']:+7.3f} {r['p_value']:10.3g}  {flag}")
    results["all_pairs"] = all_pairs
    results["bonferroni_alpha"] = bonf
    print("\n  *** survives Bonferroni correction   * raw p < alpha")

    banner("Severity distribution test")
    results["severity_mannwhitney"] = severity_test(skills, args.alpha)

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "hypothesis_tests.json").write_text(json.dumps(results, indent=2))
    print(f"\nMachine-readable summary -> {outdir/'hypothesis_tests.json'}")


if __name__ == "__main__":
    main()
