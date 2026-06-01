"""Attack-pattern taxonomy and CSV label normalization."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Pattern:
    code: str            # canonical code, e.g. "E1"
    name: str            # display name
    phase: str           # kill chain phase
    severity: str        # CRITICAL | HIGH | MEDIUM | LOW
    mitre: str           # MITRE ATT&CK technique id + name


# Severity tier -> numeric score (used by the Mann-Whitney severity test).
SEVERITY_SCORE = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}

# Canonical attack-pattern taxonomy.
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

# Kill chain phase ordering.
PHASE_ORDER = [
    "Reconnaissance",
    "Credential Access",
    "Execution",
    "Defense Evasion",
    "Exfiltration",
    "Impact",
]

# Matrix and figure display order.
CANONICAL_ORDER = [
    "E3", "E4",            # Reconnaissance
    "E2", "PE3",           # Credential Access
    "SC1", "SC2",          # Execution
    "SC3", "P2",           # Defense Evasion
    "E1", "P3",            # Exfiltration
    "P1", "P4", "PE1", "PE2",  # Impact
]

# CSV label normalization.
NAME_TO_CODE: dict[str, str] = {
    "External Transmission": "E1",
    "Network sniffing / Credential theft": "E2",
    "File System Scan": "E3",
    "Network Reconnaissance": "E4",
    "Instruction Override": "P1",
    "Hidden Instructions": "P2",
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
    """Map a raw CSV pattern label to its canonical code."""
    return NAME_TO_CODE.get(name.strip(), name.strip())


def label_for(code: str) -> str:
    """Human-readable label for a code (for axis/legend rendering)."""
    if code in TAXONOMY:
        return f"{code}: {TAXONOMY[code].name}"
    return code
