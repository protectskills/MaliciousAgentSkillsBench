#!/usr/bin/env python3
"""Generate a kill chain phase co-occurrence matrix.

Usage:
    python3 phase_cooccurrence.py
    python3 phase_cooccurrence.py --csv ../../data/malicious_skills.csv --outdir out/
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

from dataset import DEFAULT_CSV, load_skills
from patterns import PHASE_ORDER, TAXONOMY


def write_matrix(path: Path, phases, matrix):
    header = "," + ",".join(phases)
    lines = [header]
    for p, row in zip(phases, matrix):
        lines.append(p + "," + ",".join("" if v is None else str(v) for v in row))
    path.write_text("\n".join(lines) + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", default=str(DEFAULT_CSV), help="path to malicious_skills.csv")
    ap.add_argument("--outdir", default="analysis_output/phase", help="output directory")
    args = ap.parse_args()

    skills = load_skills(args.csv)
    N = len(skills)
    code2phase = {c: TAXONOMY[c].phase for c in TAXONOMY}

    members = defaultdict(set)
    for i, s in enumerate(skills):
        for ph in {code2phase[c] for c in s.codes if c in code2phase}:
            members[ph].add(i)

    print(f"Loaded {N} confirmed malicious skills.\n")
    print("Kill chain phase co-occurrence (number of skills exhibiting both phases)\n")

    abbr = {p: p[:6] for p in PHASE_ORDER}
    head = f"{'':<8}" + "".join(f"{abbr[p]:>8}" for p in PHASE_ORDER)
    print(head)
    # lower-triangular matrix (symmetric); diagonal = phase totals
    matrix = []
    for a in PHASE_ORDER:
        row = []
        line = f"{abbr[a]:<8}"
        for b in PHASE_ORDER:
            if PHASE_ORDER.index(b) > PHASE_ORDER.index(a):
                row.append(None)
                line += f"{'':>8}"
            else:
                v = len(members[a] & members[b])
                row.append(v)
                line += f"{v:>8}"
        matrix.append(row)
        print(line)

    print("\nPer-phase totals (diagonal):")
    for p in PHASE_ORDER:
        m = len(members[p])
        print(f"  {p:<18} {m:>4} ({100*m/N:.1f}%)")

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    write_matrix(outdir / "phase_cooccurrence.csv", PHASE_ORDER, matrix)
    print(f"\nMatrix written to {outdir/'phase_cooccurrence.csv'}")


if __name__ == "__main__":
    main()
