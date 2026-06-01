#!/usr/bin/env python3
"""Generate co-occurrence network statistics from ``data/malicious_skills.csv``.

Requires networkx (see requirements.txt).

Usage:
    python3 network_analysis.py
    python3 network_analysis.py --csv ../../data/malicious_skills.csv --outdir out/
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from itertools import combinations
from pathlib import Path

import networkx as nx

from dataset import DEFAULT_CSV, load_skills


def build_graph(skills):
    weights = defaultdict(int)
    nodes = set()
    for s in skills:
        nodes |= s.codes
        for a, b in combinations(sorted(s.codes), 2):
            weights[(a, b)] += 1
    g = nx.Graph()
    g.add_nodes_from(nodes)
    for (a, b), w in weights.items():
        g.add_edge(a, b, weight=w)
    return g


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", default=str(DEFAULT_CSV), help="path to malicious_skills.csv")
    ap.add_argument("--outdir", default="analysis_output/network", help="output directory")
    ap.add_argument("--seed", type=int, default=42, help="Louvain random seed")
    args = ap.parse_args()

    skills = load_skills(args.csv)
    g = build_graph(skills)
    print(f"Loaded {len(skills)} confirmed malicious skills.")
    print(f"Graph: {g.number_of_nodes()} nodes, {g.number_of_edges()} edges\n")

    wdeg = {n: sum(d["weight"] for _, _, d in g.edges(n, data=True)) for n in g}
    print("[Weighted degree (hub ranking)]")
    for n, w in sorted(wdeg.items(), key=lambda x: -x[1]):
        print(f"  {n:4s} {w}")

    bet_u = nx.betweenness_centrality(g, weight=None, normalized=True)
    gd = nx.Graph()
    for a, b, d in g.edges(data=True):
        gd.add_edge(a, b, weight=1.0 / d["weight"])
    bet_w = nx.betweenness_centrality(gd, weight="weight", normalized=True)
    print("\n[Betweenness centrality]   (unweighted | weighted dist=1/w)")
    for n in sorted(g, key=lambda n: -bet_w.get(n, 0)):
        print(f"  {n:4s} {bet_u.get(n,0):.3f} | {bet_w.get(n,0):.3f}")

    communities = nx.community.louvain_communities(g, weight="weight", seed=args.seed)
    communities = [sorted(c) for c in communities]
    print(f"\n[Louvain communities (weighted, seed={args.seed})]")
    for i, c in enumerate(communities, 1):
        print(f"  community {i}: {{{', '.join(c)}}}")

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    summary = {
        "n_nodes": g.number_of_nodes(),
        "n_edges": g.number_of_edges(),
        "weighted_degree": dict(sorted(wdeg.items(), key=lambda x: -x[1])),
        "betweenness_unweighted": {n: round(bet_u[n], 4) for n in sorted(bet_u, key=lambda n: -bet_u[n])},
        "betweenness_weighted": {n: round(bet_w[n], 4) for n in sorted(bet_w, key=lambda n: -bet_w[n])},
        "louvain_communities": communities,
    }
    (outdir / "network.json").write_text(json.dumps(summary, indent=2))
    print(f"\nMachine-readable summary -> {outdir/'network.json'}")


if __name__ == "__main__":
    main()
