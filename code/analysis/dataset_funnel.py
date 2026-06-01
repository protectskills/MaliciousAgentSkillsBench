#!/usr/bin/env python3
"""Generate the per-source dataset funnel from ``data/skills_dataset.csv``.

Usage:
    python3 dataset_funnel.py
    python3 dataset_funnel.py --csv ../../data/skills_dataset.csv
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

DEFAULT_SNAPSHOT_CSV = Path(__file__).resolve().parents[2] / "data" / "skills_dataset.csv"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", default=str(DEFAULT_SNAPSHOT_CSV), help="path to skills_dataset.csv")
    args = ap.parse_args()

    snapshot = defaultdict(int)
    suspicious = defaultdict(int)
    malicious = defaultdict(int)
    repos = defaultdict(set)
    urls = defaultdict(set)

    with Path(args.csv).open(newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            src = r["source"].strip()
            cls = r["classification"].strip()
            snapshot[src] += 1
            repos[src].add(r["repo"].strip())
            if r.get("url"):
                urls[src].add(r["url"].strip())
            if cls == "suspicious":
                suspicious[src] += 1
            elif cls == "malicious":
                malicious[src] += 1

    sources = sorted(snapshot)
    header = f"{'Source':<14}{'Repos':>8}{'Snapshot':>10}{'Candidates':>12}{'Confirmed':>11}"
    print(header)
    print("-" * len(header))
    tot = dict(repos=0, snap=0, cand=0, conf=0, urls=0)
    for src in sources:
        cand = suspicious[src] + malicious[src]
        print(f"{src:<14}{len(repos[src]):>8}{snapshot[src]:>10}{cand:>12}{malicious[src]:>11}")
        tot["repos"] += len(repos[src]); tot["snap"] += snapshot[src]
        tot["cand"] += cand; tot["conf"] += malicious[src]; tot["urls"] += len(urls[src])
    print("-" * len(header))
    print(f"{'Total':<14}{tot['repos']:>8}{tot['snap']:>10}{tot['cand']:>12}{tot['conf']:>11}")

    print("\nRepository identifier = distinct `repo` column values.")
    print("Distinct source URLs (reference): "
          + ", ".join(f"{src}={len(urls[src])}" for src in sources)
          + f", total={tot['urls']}")
    print(f"\nCandidate rate: {tot['cand']}/{tot['snap']} = {100*tot['cand']/tot['snap']:.1f}% of snapshot")
    print(f"Confirmed rate: {tot['conf']}/{tot['cand']} = {100*tot['conf']/tot['cand']:.1f}% of candidates; "
          f"{tot['conf']}/{tot['snap']} = {100*tot['conf']/tot['snap']:.2f}% of snapshot")


if __name__ == "__main__":
    main()
