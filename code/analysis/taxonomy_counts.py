#!/usr/bin/env python3
"""Generate instance-level attack-technique taxonomy counts.

Usage:
    python3 taxonomy_counts.py
    python3 taxonomy_counts.py --csv ../../data/malicious_skills.csv
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path

from patterns import PHASE_ORDER, TAXONOMY, normalize_pattern

DEFAULT_CSV = Path(__file__).resolve().parents[2] / "data" / "malicious_skills.csv"


def load_counts(csv_path: Path | str = DEFAULT_CSV):
    """Return instance counts, per-code skill sets, and the skill count."""
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Dataset not found: {csv_path}")
    instances: Counter = Counter()
    skills: dict[str, set] = defaultdict(set)
    skillset: set = set()
    with csv_path.open(newline="") as f:
        reader = csv.DictReader(f)
        required = {"repo", "skill_name", "Pattern"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"CSV missing required columns: {sorted(missing)}")
        for r in reader:
            key = (r["repo"].strip(), r["skill_name"].strip())
            skillset.add(key)
            for raw in r["Pattern"].split(";"):
                raw = raw.strip()
                if not raw:
                    continue
                code = normalize_pattern(raw)
                instances[code] += 1
                skills[code].add(key)
    return instances, skills, len(skillset)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", default=str(DEFAULT_CSV), help="path to malicious_skills.csv")
    args = ap.parse_args()

    instances, skills, n_skills = load_counts(args.csv)
    total = sum(instances.values())

    print(f"Instance-level attack-technique taxonomy "
          f"({total} vulnerability instances across {n_skills} confirmed malicious skills)\n")
    header = f"{'Phase':<18}{'ID':<5}{'Technique':<38}{'Sev':<6}{'Inst':>5}{'%':>7}{'Skills':>8}"
    print(header)
    print("-" * len(header))

    by_phase: dict[str, list[str]] = {}
    for code, pat in TAXONOMY.items():
        by_phase.setdefault(pat.phase, []).append(code)

    for phase in PHASE_ORDER:
        for code in by_phase.get(phase, []):
            pat = TAXONOMY[code]
            cnt = instances.get(code, 0)
            sk = len(skills.get(code, set()))
            pct = 100 * cnt / total if total else 0.0
            print(f"{phase:<18}{code:<5}{pat.name[:36]:<38}{pat.severity:<6}{cnt:>5}{pct:>6.1f}%{sk:>8}")

    print("-" * len(header))
    print(f"{'TOTAL':<18}{'':<5}{'':<38}{'':<6}{total:>5}{100.0:>6.1f}%{n_skills:>8}")
    print("\n(Inst = instance count; Skills = per-skill count.)")

    extra = sorted(c for c in instances if c not in TAXONOMY)
    if extra:
        print("\nNon-taxonomy codes present (unexpected):",
              ", ".join(f"{c}={instances[c]}" for c in extra))


if __name__ == "__main__":
    main()
