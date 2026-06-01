"""Load normalized attack-pattern data from ``data/malicious_skills.csv``."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

from patterns import (
    SEVERITY_SCORE,
    TAXONOMY,
    normalize_pattern,
)

DEFAULT_CSV = Path(__file__).resolve().parents[2] / "data" / "malicious_skills.csv"


@dataclass
class Skill:
    source: str
    repo: str
    skill_name: str
    codes: set[str] = field(default_factory=set)
    severities: list[int] = field(default_factory=list)

    def severity_score(self) -> float:
        """Return the mean instance severity or the highest taxonomy fallback."""
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
    """Return present codes in display order."""
    from patterns import CANONICAL_ORDER

    seen = set()
    for s in skills:
        seen |= s.codes

    ordered: list[str] = [c for c in CANONICAL_ORDER if c in seen]
    known = set(ordered)
    ordered += sorted(c for c in seen if c not in known)
    return ordered
