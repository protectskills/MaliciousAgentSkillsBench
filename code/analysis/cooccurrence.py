#!/usr/bin/env python3
"""Co-occurrence matrix generation (paper RQ2 / Section 5.4).

Reproduces, from the released ``data/malicious_skills.csv``:

  * the pattern co-occurrence count matrix (Appendix Table "Pattern
    Co-occurrence Matrix"), where the diagonal is the number of skills
    exhibiting each pattern and off-diagonal cells count skills exhibiting
    both patterns;
  * the conditional-probability matrix  P(P_j | P_i)  (Eq. "cond_prob");
  * the odds-ratio matrix  OR(P_i, P_j)  (Eq. "odds_ratio");
  * the phi-coefficient matrix; and
  * the co-occurrence heatmap for the five patterns in the paper figure
    (E1, E2, P1, P4, SC2; fixed via ``FIGURE_CODES``).

Outputs (written under --outdir, default ``analysis_output/cooccurrence``):
    cooccurrence_counts.csv        Symmetric count matrix (diagonal = totals).
    conditional_probability.csv    Row-conditional P(col | row).
    odds_ratio.csv                 Pairwise odds ratios.
    phi.csv                        Pairwise phi coefficients.
    pattern_cooccurrence.pdf/.png  Heatmap for the five fixed figure patterns.

Usage:
    python3 cooccurrence.py
    python3 cooccurrence.py --canonical-only
    python3 cooccurrence.py --csv ../../data/malicious_skills.csv --outdir out/
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np

from dataset import DEFAULT_CSV, load_skills, present_codes
from patterns import label_for


def build_incidence(skills, codes):
    """Return an (n_skills x n_codes) 0/1 incidence matrix."""
    index = {c: i for i, c in enumerate(codes)}
    inc = np.zeros((len(skills), len(codes)), dtype=int)
    for r, s in enumerate(skills):
        for c in s.codes:
            if c in index:
                inc[r, index[c]] = 1
    return inc


def cooccurrence_counts(inc):
    """Symmetric co-occurrence counts; diagonal = per-pattern totals."""
    return inc.T @ inc


def conditional_probability(counts):
    """P(col | row) = n(row & col) / n(row)."""
    totals = np.diag(counts).astype(float)
    with np.errstate(divide="ignore", invalid="ignore"):
        cond = counts / totals[:, None]
    cond[~np.isfinite(cond)] = 0.0
    return cond


def odds_ratio_matrix(inc, counts):
    """OR(i, j) = (n11 * n00) / (n10 * n01) using Haldane-Anscombe 0.5
    correction for zero cells. Diagonal set to NaN."""
    n = inc.shape[0]
    k = counts.shape[0]
    totals = np.diag(counts)
    out = np.full((k, k), np.nan)
    for i in range(k):
        for j in range(k):
            if i == j:
                continue
            n11 = counts[i, j]
            n10 = totals[i] - n11
            n01 = totals[j] - n11
            n00 = n - n11 - n10 - n01
            a, b, c, d = n11 + 0.5, n10 + 0.5, n01 + 0.5, n00 + 0.5
            out[i, j] = (a * d) / (b * c)
    return out


def phi_matrix(inc, counts):
    """Phi (mean-square contingency) coefficient per pair. Diagonal = 1."""
    n = inc.shape[0]
    k = counts.shape[0]
    totals = np.diag(counts).astype(float)
    out = np.zeros((k, k))
    for i in range(k):
        for j in range(k):
            if i == j:
                out[i, j] = 1.0
                continue
            n11 = counts[i, j]
            n1_ = totals[i]
            n_1 = totals[j]
            n10 = n1_ - n11
            n01 = n_1 - n11
            n00 = n - n11 - n10 - n01
            denom = math.sqrt(n1_ * (n - n1_) * n_1 * (n - n_1))
            out[i, j] = (n11 * n00 - n10 * n01) / denom if denom > 0 else 0.0
    return out


def write_matrix(path: Path, codes, matrix, fmt="%g"):
    header = "," + ",".join(codes)
    lines = [header]
    for c, row in zip(codes, matrix):
        cells = []
        for v in row:
            if isinstance(v, float) and math.isnan(v):
                cells.append("")
            else:
                cells.append(fmt % v)
        lines.append(c + "," + ",".join(cells))
    path.write_text("\n".join(lines) + "\n")


# Patterns shown in the published figure (Figure "Pattern co-occurrence matrix
# (five most prevalent patterns)").
FIGURE_CODES = ["E1", "E2", "P1", "P4", "SC2"]


def render_heatmap(path_stem: Path, codes, counts):
    """Render the co-occurrence heatmap for the five patterns in the paper Figure
    'Pattern co-occurrence matrix (five most prevalent patterns)'."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    index = {c: i for i, c in enumerate(codes)}
    sub_codes = [c for c in FIGURE_CODES if c in index]
    n = len(sub_codes)
    order = [index[c] for c in sub_codes]
    sub = counts[np.ix_(order, order)]

    fig, ax = plt.subplots(figsize=(1.2 * n + 1.5, 1.2 * n + 1.0))
    im = ax.imshow(sub, cmap="YlOrRd")
    ax.set_xticks(range(n))
    ax.set_yticks(range(n))
    ax.set_xticklabels(sub_codes)
    ax.set_yticklabels(sub_codes)
    ax.set_title("Pattern co-occurrence matrix (five most prevalent patterns)")
    for i in range(n):
        for j in range(n):
            val = sub[i, j]
            ax.text(
                j, i, str(int(val)),
                ha="center", va="center",
                color="white" if val > sub.max() * 0.6 else "black",
                fontsize=9,
            )
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="skills with both patterns")
    fig.tight_layout()
    for ext in ("pdf", "png"):
        fig.savefig(path_stem.with_suffix("." + ext), bbox_inches="tight")
    plt.close(fig)
    return sub_codes


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", default=str(DEFAULT_CSV), help="path to malicious_skills.csv")
    ap.add_argument("--outdir", default="analysis_output/cooccurrence", help="output directory")
    ap.add_argument("--canonical-only", action="store_true",
                    help="restrict to the 14-pattern taxonomy (drop any non-taxonomy scanner labels)")
    ap.add_argument("--no-figure", action="store_true", help="skip heatmap rendering")
    args = ap.parse_args()

    skills = load_skills(args.csv, canonical_only=args.canonical_only)
    codes = present_codes(skills, canonical_only=args.canonical_only)
    inc = build_incidence(skills, codes)
    counts = cooccurrence_counts(inc)
    cond = conditional_probability(counts)
    orm = odds_ratio_matrix(inc, counts)
    phi = phi_matrix(inc, counts)

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    write_matrix(outdir / "cooccurrence_counts.csv", codes, counts, fmt="%d")
    write_matrix(outdir / "conditional_probability.csv", codes, cond, fmt="%.4f")
    write_matrix(outdir / "odds_ratio.csv", codes, orm, fmt="%.4f")
    write_matrix(outdir / "phi.csv", codes, phi, fmt="%.4f")

    print(f"Loaded {len(skills)} confirmed malicious skills.")
    print(f"Patterns present ({len(codes)}): {', '.join(codes)}")
    print("\nPer-pattern skill counts (matrix diagonal):")
    totals = np.diag(counts)
    for c, t in sorted(zip(codes, totals), key=lambda x: -x[1]):
        print(f"  {label_for(c):48s} {t}")

    if not args.no_figure:
        sub_codes = render_heatmap(outdir / "pattern_cooccurrence", codes, counts)
        print(f"\nHeatmap ({', '.join(sub_codes)}) -> "
              f"{outdir/'pattern_cooccurrence.pdf'}")

    print(f"\nMatrices written to {outdir}/")


if __name__ == "__main__":
    main()
