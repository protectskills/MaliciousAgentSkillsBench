"""Single source of truth for the attack-pattern taxonomy used in RQ2 analysis.

This module mirrors the 14-pattern taxonomy from the paper (Table:
"Attack Technique Taxonomy" and Appendix "Attack Taxonomy MITRE ATT&CK
Mapping") and provides the mapping from the human-readable pattern names used
in the released ``data/malicious_skills.csv`` to the canonical pattern codes
(E*, P*, PE*, SC*).

The released CSV labels each confirmed malicious skill with a semicolon-
separated ``Pattern`` column (scanner-facing display names) plus an aligned
``Severity`` column (one CRITICAL/HIGH/MEDIUM/LOW rating per token). Pattern
tokens repeat once per vulnerability instance, so one file supports two
granularities: summed WITHOUT dedup it reproduces the paper's 632 instance-level
taxonomy counts (``taxonomy_counts.py``); deduped per skill it drives the
co-occurrence matrix and the Fisher / severity tests (``cooccurrence.py``,
``hypothesis_tests.py``). The scripts normalize display names to the canonical
codes below.

Note on coverage: of the 14 defined patterns, E4 (Network Reconnaissance) is
absent from every confirmed malicious skill (see paper Section 4), so it has
zero rows in the released CSV.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Pattern:
    code: str            # canonical code, e.g. "E1"
    name: str            # paper display name
    phase: str           # kill chain phase
    severity: str        # CRITICAL | HIGH | MEDIUM | LOW
    mitre: str           # MITRE ATT&CK technique id + name


# Severity tier -> numeric score (used by the Mann-Whitney severity test).
SEVERITY_SCORE = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}

# Canonical 14-pattern taxonomy (paper Table "Attack Technique Taxonomy" +
# Appendix MITRE mapping + Appendix "Severity Assignment Criteria").
TAXONOMY: dict[str, Pattern] = {
    p.code: p
    for p in [
        Pattern("E1", "External Transmission", "Exfiltration", "HIGH", "T1041 Exfiltration Over C2 Channel"),
        Pattern("E2", "Credential Harvesting", "Credential Access", "CRITICAL", "T1552 Unsecured Credentials"),
        Pattern("E3", "File System Enumeration", "Reconnaissance", "MEDIUM", "T1083 File and Directory Discovery"),
        Pattern("E4", "Network Reconnaissance", "Reconnaissance", "MEDIUM", "T1046 Network Service Discovery"),
        Pattern("P1", "Instruction Override", "Impact", "HIGH", "T1059 Command and Scripting Interpreter"),
        Pattern("P2", "Hidden Instructions", "Defense Evasion", "HIGH", "T1027 Obfuscated Files or Information"),
        Pattern("P3", "Context Leakage and Data Exfiltration", "Exfiltration", "HIGH", "T1020 Automated Exfiltration"),
        Pattern("P4", "Behavior Manipulation", "Impact", "MEDIUM", "T1059 Command and Scripting Interpreter"),
        Pattern("PE1", "Excessive Permissions", "Impact", "LOW", "T1068 Exploitation for Privilege Escalation"),
        Pattern("PE2", "Privilege Escalation", "Impact", "MEDIUM", "T1548 Abuse Elevation Control Mechanism"),
        Pattern("PE3", "Credential File Access", "Credential Access", "CRITICAL", "T1555 Credentials from Password Stores"),
        Pattern("SC1", "Command Injection", "Execution", "HIGH", "T1059 Command and Scripting Interpreter"),
        Pattern("SC2", "Remote Script Execution", "Execution", "CRITICAL", "T1105 Ingress Tool Transfer"),
        Pattern("SC3", "Obfuscated Code", "Defense Evasion", "CRITICAL", "T1027 Obfuscated Files or Information"),
    ]
}

# Kill chain phase ordering (paper taxonomy table, top to bottom).
PHASE_ORDER = [
    "Reconnaissance",
    "Credential Access",
    "Execution",
    "Defense Evasion",
    "Exfiltration",
    "Impact",
]

# Canonical display order for matrices/figures: group by kill chain phase.
CANONICAL_ORDER = [
    "E3", "E4",            # Reconnaissance
    "E2", "PE3",           # Credential Access
    "SC1", "SC2",          # Execution
    "SC3", "P2",           # Defense Evasion
    "E1", "P3",            # Exfiltration
    "P1", "P4", "PE1", "PE2",  # Impact
]

# Mapping from the released CSV's display names to canonical codes.
# Source: scanner display names in data/malicious_skills.csv `Pattern` column.
NAME_TO_CODE: dict[str, str] = {
    "External Transmission": "E1",
    "Network sniffing / Credential theft": "E2",
    "File System Scan": "E3",
    "Network Reconnaissance": "E4",
    "Instruction Override": "P1",
    "Hidden Instructions": "P2",
    # P3 in the paper is "Context Leakage and Data Exfiltration"; the scanner
    # emits the two facets as separate labels that both map to P3.
    "Context Leakage": "P3",
    "Data Exfiltration": "P3",
    "Behavior Manipulation": "P4",
    "Excessive Permissions": "PE1",
    "Privilege Escalation": "PE2",
    "Hardcoded Tokens": "PE3",
    "Command Injection": "SC1",
    "Remote Code Execution": "SC2",
    "Code Obfuscation": "SC3",
}


def normalize_pattern(name: str) -> str:
    """Map a raw CSV pattern label to its canonical code.

    Unknown labels are returned verbatim so that input is never silently
    dropped; such labels surface in the output and can be added to
    ``NAME_TO_CODE`` if a registry introduces a new scanner name.
    """
    return NAME_TO_CODE.get(name.strip(), name.strip())


def label_for(code: str) -> str:
    """Human-readable label for a code (for axis/legend rendering)."""
    if code in TAXONOMY:
        return f"{code}: {TAXONOMY[code].name}"
    return code
