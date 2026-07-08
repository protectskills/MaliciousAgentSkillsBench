#!/usr/bin/env python3
"""E1 dataset check: report the released CSV counts (stdlib only, no deps)."""
import collections
import csv
from pathlib import Path

DATA = Path(__file__).resolve().parents[2] / "data"


def counts(name, col="classification"):
    with (DATA / name).open(newline="") as f:
        return collections.Counter(r[col] for r in csv.DictReader(f))


mal = counts("malicious_skills.csv")
by_source = counts("malicious_skills.csv", "source")
snap = counts("skills_dataset.csv")

print(f"malicious_skills.csv : {sum(mal.values())} rows  {dict(by_source)}")
print(f"skills_dataset.csv   : {dict(snap)}  total={sum(snap.values())}")
print(f"Tier-2 candidates    : suspicious + malicious = "
      f"{snap['suspicious'] + snap['malicious']}")
