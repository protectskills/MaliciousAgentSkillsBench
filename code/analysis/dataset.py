"""Loader for the released confirmed-malicious dataset.

Reads ``data/malicious_skills.csv`` and returns, for each of the 157 confirmed
malicious skills, the set of canonical attack-pattern codes it exhibits. This
is the shared input for both ``cooccurrence.py`` and ``hypothesis_tests.py``.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

from patterns import (
    SEVERITY_SCORE,
    TAXONOMY,
    normalize_pattern,
)

# Default location of the released CSV relative to this file:
# code/analysis/dataset.py -> ../../data/malicious_skills.csv
DEFAULT_CSV = Path(__file__).resolve().parents[2] / "data" / "malicious_skills.csv"


@dataclass
class Skill:
    source: str
    repo: str
    skill_name: str
    codes: set[str] = field(default_factory=set)
    severities: list[int] = field(default_factory=list)

    def severity_score(self) -> float:
        """Skill severity = mean of its per-instance, analyst-assigned severity
        ratings. The paper's H2 test averages the CRITICAL/HIGH/MEDIUM/LOW rating
        labeled for each vulnerability instance (see the per-instance ``Severity``
        column of malicious_skills.csv, aligned one-to-one with ``Pattern``).
        Falls back to the max per-pattern taxonomy tier only when the per-instance
        ``Severity`` column is absent.
        """
        if self.severities:
            return sum(self.severities) / len(self.severities)
        scores = [
            SEVERITY_SCORE[TAXONOMY[c].severity]
            for c in self.codes
            if c in TAXONOMY
        ]
        return max(scores) if scores else 0


def load_skills(csv_path: Path | str = DEFAULT_CSV, canonical_only: bool = False) -> list[Skill]:
    """Load confirmed malicious skills with normalized pattern codes.

    Args:
        csv_path: path to malicious_skills.csv.
        canonical_only: if True, drop any label outside the 14-pattern taxonomy.
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Dataset not found: {csv_path}")

    skills: list[Skill] = []
    with csv_path.open(newline="") as f:
        reader = csv.DictReader(f)
        required = {"source", "repo", "skill_name", "Pattern"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"CSV missing required columns: {sorted(missing)}")
        for row in reader:
            codes = set()
            for raw in row["Pattern"].split(";"):
                raw = raw.strip()
                if not raw:
                    continue
                code = normalize_pattern(raw)
                if canonical_only and code not in TAXONOMY:
                    continue
                codes.add(code)
            severities = []
            for raw in (row.get("Severity") or "").split(";"):
                tier = raw.strip().upper()
                if tier in SEVERITY_SCORE:
                    severities.append(SEVERITY_SCORE[tier])
            skills.append(
                Skill(
                    source=row["source"].strip(),
                    repo=row["repo"].strip(),
                    skill_name=row["skill_name"].strip(),
                    codes=codes,
                    severities=severities,
                )
            )
    return skills


def present_codes(skills: list[Skill], canonical_only: bool = False) -> list[str]:
    """Return codes present in the data, in canonical display order, with any
    unexpected/unknown codes appended at the end (sorted)."""
    from patterns import CANONICAL_ORDER

    seen = set()
    for s in skills:
        seen |= s.codes

    ordered: list[str] = [c for c in CANONICAL_ORDER if c in seen]
    # Any code not accounted for (unknown scanner label) appended last.
    known = set(ordered)
    ordered += sorted(c for c in seen if c not in known)
    return ordered
