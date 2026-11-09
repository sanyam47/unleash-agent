"""
Automated AppSec Vulnerability & Secret Leakage Scanner.
Addresses AppSec & Compliance requirements (Marcus Kane):
  1. Detects hardcoded secrets, private tokens, and API keys before deployment.
  2. Flags dangerous dynamic execution sinks: eval(), new Function(), document.write().
  3. Detects mixed content (http:// script resources) and reverse-tabnabbing vulnerabilities.
  4. Returns structured findings with file provenance, line numbers, and prescriptive fixes.
"""

import re
from pathlib import Path
from typing import Dict, Any, List

# Regex patterns for credential & token leakage
SECRET_PATTERNS = [
    ("openai_api_key", r"\bsk-[a-zA-Z0-9_\-]{20,}\b", "Hardcoded OpenAI API Key"),
    ("github_token", r"\b(?:ghp|gho|ghu|ghs|ghr)_[a-zA-Z0-9]{20,}\b", "Hardcoded GitHub Personal Token"),
    ("aws_access_key", r"\bAKIA[0-9A-Z]{16}\b", "Hardcoded AWS Access Key ID"),
    ("runpod_key", r"\brpa_[a-zA-Z0-9_\-]{20,}\b", "Hardcoded RunPod API Token"),
    ("generic_secret", r"(?:api_key|apikey|secret_key|auth_token|client_secret)\s*[:=]\s*['\"][a-zA-Z0-9_\-]{16,}['\"]", "Hardcoded Generic Secret Token"),
    ("private_key_header", r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", "Hardcoded Asymmetric Private Key")
]

# Regex patterns for dangerous execution and injection
DANGEROUS_PATTERNS = [
    ("eval_sink", r"\beval\s*\(", "Dangerous eval() Execution Sink", "Use JSON.parse() or structured handlers instead of dynamic code evaluation."),
    ("function_constructor", r"new\s+Function\s*\(", "Dangerous Function() Constructor", "Avoid dynamic function creation from strings; bind directly to modular functions."),
    ("document_write", r"document\.write\s*\(", "Dangerous document.write() Sink", "Use document.createElement() or textContent/appendChild to avoid DOM XSS."),
]


def audit_workspace_security(proj_dir: Path) -> Dict[str, Any]:
    """
    Scans all source files in the project workspace for AppSec vulnerabilities.
    Returns validation status and actionable diagnostic findings.
    """
    findings: List[Dict[str, Any]] = []

    if not proj_dir.exists() or not proj_dir.is_dir():
        return {
            "valid": True,
            "findings": [],
            "critical_count": 0,
            "high_count": 0,
            "summary": "Workspace directory does not exist or is empty."
        }

    scannable_extensions = {".html", ".js", ".py", ".json", ".css", ".ts", ".jsx", ".tsx"}
    files = [f for f in proj_dir.rglob("*") if f.is_file() and f.suffix.lower() in scannable_extensions]

    for file_path in files:
        # Skip snapshots or test artifacts
        if ".snapshots" in file_path.parts or "node_modules" in file_path.parts or ".git" in file_path.parts:
            continue

        rel_path = str(file_path.relative_to(proj_dir)).replace("\\", "/")
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()
        except Exception:
            continue

        # 1. Scan for hardcoded secrets
        for pat_name, regex_str, title in SECRET_PATTERNS:
            for line_idx, line in enumerate(lines, start=1):
                # Ignore comment-only explanations
                stripped = line.strip()
                if stripped.startswith("//") or stripped.startswith("#") or stripped.startswith("*"):
                    continue

                match = re.search(regex_str, line, re.IGNORECASE)
                if match:
                    findings.append({
                        "file": rel_path,
                        "line": line_idx,
                        "severity": "CRITICAL",
                        "category": "secret_leakage",
                        "title": title,
                        "snippet": line[:100].strip(),
                        "remediation": "Do not hardcode API keys or secrets in source files. Use the Encrypted Credential Vault (POST /vault/secret) or environment variables."
                    })

        # 2. Scan JavaScript files for dangerous execution sinks
        if file_path.suffix.lower() in (".js", ".ts", ".html"):
            for pat_name, regex_str, title, remediation in DANGEROUS_PATTERNS:
                for line_idx, line in enumerate(lines, start=1):
                    stripped = line.strip()
                    if stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
                        continue
                    if re.search(regex_str, line):
                        findings.append({
                            "file": rel_path,
                            "line": line_idx,
                            "severity": "HIGH",
                            "category": "code_injection",
                            "title": title,
                            "snippet": line[:100].strip(),
                            "remediation": remediation
                        })

        # 3. Scan HTML files for insecure external scripts & tabnabbing
        if file_path.suffix.lower() == ".html":
            for line_idx, line in enumerate(lines, start=1):
                # Insecure HTTP scripts
                if re.search(r'<script\s+[^>]*src=["\']http://', line, re.IGNORECASE):
                    findings.append({
                        "file": rel_path,
                        "line": line_idx,
                        "severity": "HIGH",
                        "category": "insecure_transport",
                        "title": "Insecure HTTP Script Resource",
                        "snippet": line[:100].strip(),
                        "remediation": "Load all external scripts securely over HTTPS or bundle them locally."
                    })
                # Tabnabbing target="_blank" without rel="noopener"
                if re.search(r'target=["\']_blank["\']', line, re.IGNORECASE):
                    if not re.search(r'rel=["\'][^"\']*noopener', line, re.IGNORECASE):
                        findings.append({
                            "file": rel_path,
                            "line": line_idx,
                            "severity": "MEDIUM",
                            "category": "tabnabbing",
                            "title": "Reverse Tabnabbing Vulnerability",
                            "snippet": line[:100].strip(),
                            "remediation": "Add rel=\"noopener noreferrer\" to all anchor tags with target=\"_blank\"."
                        })

    critical_count = sum(1 for f in findings if f["severity"] == "CRITICAL")
    high_count = sum(1 for f in findings if f["severity"] == "HIGH")
    is_valid = (critical_count == 0 and high_count == 0)

    summary = (
        "Security audit passed cleanly. Zero critical vulnerabilities or leaked credentials detected."
        if is_valid else
        f"Security audit flagged {critical_count} critical and {high_count} high-severity vulnerabilities requiring remediation."
    )

    return {
        "valid": is_valid,
        "findings": findings,
        "critical_count": critical_count,
        "high_count": high_count,
        "total_findings": len(findings),
        "summary": summary
    }
