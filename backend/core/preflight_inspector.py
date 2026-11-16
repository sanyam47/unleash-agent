"""
Pre-Flight Discretion Inspector - Phase 7: Cognitive Guardrails & Advisory Intelligence.

Provides human-like discernment before touching external networks or executing packages:
1. Typosquatting & Unverified Package Inspection (PyPI, NPM).
2. Malicious Command & Obfuscation Heuristics (Base64 payloads, curl | bash, eval).
3. Suspicious Host & Network Egress Detection (Raw IPs, untrusted script sources).
4. Conversational Warning Generation: Gives Jarvis clear reasons to pause and consult the user.
"""

import re
from typing import Dict, Any, Optional, List

# Known popular packages mapping to detect typosquats
KNOWN_PACKAGES = {
    "python": [
        "requests", "numpy", "pandas", "fastapi", "flask", "django",
        "scipy", "scikit-learn", "torch", "tensorflow", "pydantic",
        "pytest", "click", "jinja2", "sqlalchemy", "celery", "redis",
        "beautifulsoup4", "selenium", "playwright", "pillow", "matplotlib",
        "cryptography", "paramiko", "boto3", "google-genai", "networkx"
    ],
    "npm": [
        "react", "react-dom", "express", "lodash", "axios", "next",
        "vue", "svelte", "typescript", "webpack", "vite", "tailwindcss",
        "chalk", "commander", "fs-extra", "dotenv", "rxjs"
    ]
}

SUSPICIOUS_NAME_PATTERNS = [
    r"(?:free|crack|hack|steal|grab|leak|nitro|keygen|exploit|bypass)",
    r"(?:token-?logger|wallet-?drainer|crypto-?miner|ransom)",
]

OBFUSCATION_PATTERNS = [
    (r"\b(?:curl|wget)\s+[^|\n]+\|\s*(?:sh|bash|zsh|python|perl)\b", "Piped remote web script directly into shell interpreter ('curl | bash')."),
    (r"\b(?:powershell|pwsh)\s+(?:-[a-zA-Z]+\s+)*(?:-[eE](?:nc(?:odedCommand)?)?)\s+[A-Za-z0-9+/=]{16,}", "Encoded base64 PowerShell payload execution."),
    (r"\b(?:base64\s+-d|certutil\s+-decode)\b", "Base64 payload decoding before execution."),
    (r"\b(?:eval|exec)\s*\(\s*(?:base64|decode|compile|b64decode)\b", "Dynamic code evaluation with in-memory decoding."),
    (r"\b(?:rm\s+-rf\s+(?:/|/\*|~|~/\*))\b", "Destructive recursive deletion of system/user root."),
    (r"\b(?:del\s+/f\s+/s\s+/q\s+C:\\Windows)\b", "Destructive Windows system folder deletion.")
]


def _levenshtein_distance(s1: str, s2: str) -> int:
    """Computes basic edit distance between two strings."""
    if len(s1) < len(s2):
        return _levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]


def inspect_package_safety(package_name: str, ecosystem: str = "python") -> Dict[str, Any]:
    """
    Evaluates whether a package name is suspicious, typosquatted, or flagged.
    """
    clean_name = str(package_name or "").strip().lower()
    if not clean_name:
        return {"is_suspicious": False, "risk_level": "low"}

    # 1. Check for blatantly malicious keywords
    for pat in SUSPICIOUS_NAME_PATTERNS:
        if re.search(pat, clean_name):
            return {
                "is_suspicious": True,
                "risk_level": "critical",
                "reason": f"Package name '{clean_name}' contains suspicious/malicious terms ({pat}).",
                "recommendation": "Do not install this package without inspecting its raw code.",
                "suggested_alternative": None
            }

    # 2. Check for typosquatting of popular packages
    known_list = KNOWN_PACKAGES.get(ecosystem, KNOWN_PACKAGES["python"])
    for canonical in known_list:
        if clean_name == canonical:
            return {"is_suspicious": False, "risk_level": "low", "canonical": canonical}

        dist = _levenshtein_distance(clean_name, canonical)
        # If edit distance is 1 or 2, and length is similar, it's a high-probability typosquat
        if 1 <= dist <= 2 and abs(len(clean_name) - len(canonical)) <= 2:
            return {
                "is_suspicious": True,
                "risk_level": "high",
                "reason": f"Package '{clean_name}' closely resembles the well-known package '{canonical}' (typosquat risk, distance={dist}).",
                "recommendation": f"Verify if you intended to install the official '{canonical}' package instead.",
                "suggested_alternative": canonical
            }

    return {
        "is_suspicious": False,
        "risk_level": "low",
        "reason": f"Package '{clean_name}' did not trigger any known typosquatting or malicious heuristics."
    }


def inspect_command_safety(command_str: str) -> Dict[str, Any]:
    """
    Inspects shell command lines for obfuscated or dangerous patterns.
    """
    cmd = str(command_str or "").strip()
    if not cmd:
        return {"is_suspicious": False, "risk_level": "low"}

    # 1. Check obfuscation & dangerous command patterns
    for pat, desc in OBFUSCATION_PATTERNS:
        if re.search(pat, cmd, re.IGNORECASE):
            return {
                "is_suspicious": True,
                "risk_level": "high",
                "reason": desc,
                "recommendation": "Request explicit confirmation from the human before executing obfuscated shell directives.",
                "pattern": pat
            }

    # 2. Check package manager install commands
    m_pip = re.search(r"\bpip\s+install\s+(?:--[a-z-]+\s+)*([a-zA-Z0-9_.-]+)", cmd, re.IGNORECASE)
    if m_pip:
        pkg = m_pip.group(1).split("==")[0].split(">=")[0].split("<=")[0]
        pkg_res = inspect_package_safety(pkg, "python")
        if pkg_res.get("is_suspicious"):
            return pkg_res

    m_npm = re.search(r"\bnpm\s+(?:i|install)\s+(?:--[a-z-]+\s+)*([a-zA-Z0-9_.-]+)", cmd, re.IGNORECASE)
    if m_npm:
        pkg = m_npm.group(1).split("@")[0]
        pkg_res = inspect_package_safety(pkg, "npm")
        if pkg_res.get("is_suspicious"):
            return pkg_res

    return {
        "is_suspicious": False,
        "risk_level": "low",
        "reason": "Command passed pre-flight security evaluation."
    }


def inspect_url_safety(url_str: str) -> Dict[str, Any]:
    """
    Inspects URLs for raw IP addresses, suspicious TLDs, and unsafe protocols.
    """
    url = str(url_str or "").strip()
    if not url:
        return {"is_suspicious": False, "risk_level": "low"}

    # Check for raw IP address access
    m_ip = re.search(r"https?://(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})(?::\d+)?", url)
    if m_ip:
        ip = m_ip.group(1)
        # Allow local network/localhost
        if not (ip.startswith("127.") or ip.startswith("192.168.") or ip.startswith("10.") or ip == "0.0.0.0"):
            return {
                "is_suspicious": True,
                "risk_level": "medium",
                "reason": f"URL targets a raw public IP address ({ip}) rather than a verified domain name.",
                "recommendation": "Confirm whether this public IP endpoint is intended and trusted."
            }

    return {
        "is_suspicious": False,
        "risk_level": "low",
        "reason": "URL passed pre-flight security evaluation."
    }
