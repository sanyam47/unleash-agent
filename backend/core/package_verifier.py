"""
Autonomous Package Authenticity & Typo-Squatting Verifier (Pre-Flight Registry Gate)

Performs automated reputation audits against official PyPI & npm registries before
Human-in-the-Loop approval cards are displayed:
  1. Registry Verification: Confirms package actually exists (prevents LLM hallucination traps).
  2. Age & Zero-Day Check: Flags packages registered less than 30 days ago.
  3. Typo-Squatting Detection: Uses Levenshtein similarity against Top-100 authoritative packages
     to warn users about deceptive lookalikes (e.g. 'collorama' vs 'colorama').
"""

import re
import json
import time
import difflib
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional, Tuple

CACHE_EXPIRY_SEC = 86400  # Cache registry lookup for 24 hours
_PACKAGE_VERIFIER_CACHE: Dict[str, Dict[str, Any]] = {}

POPULAR_PYPI_PACKAGES = [
    "requests", "numpy", "pandas", "scipy", "matplotlib", "flask", "fastapi",
    "django", "urllib3", "pydantic", "pytest", "scikit-learn", "torch", "tensorflow",
    "beautifulsoup4", "selenium", "colorama", "cryptography", "sqlalchemy", "httpx",
    "aiohttp", "certifi", "wheel", "setuptools", "uvicorn", "jinja2", "click",
    "pillow", "pytest-asyncio", "celery", "pyyaml", "redis", "pymongo", "psycopg2"
]

POPULAR_NPM_PACKAGES = [
    "express", "react", "react-dom", "vue", "axios", "lodash", "chalk", "commander",
    "webpack", "typescript", "next", "dotenv", "cors", "body-parser", "moment",
    "fs-extra", "glob", "inquirer", "rxjs", "eslint", "jest", "prettier", "vite"
]


def extract_package_names(command: str) -> List[Tuple[str, str]]:
    """
    Parses a shell command and extracts (ecosystem, package_name) pairs.
    Example: 'pip install fastapi uvicorn' -> [('pypi', 'fastapi'), ('pypi', 'uvicorn')]
    """
    lowered = command.strip().lower()
    results = []

    # Strip flags like -U, --upgrade, -r, --ignore-scripts, etc.
    clean_cmd = re.sub(r"--?[a-zA-Z0-9_\-]+(?:=[^\s]+)?", "", command).strip()
    tokens = clean_cmd.split()

    if not tokens:
        return results

    if any(tok in lowered for tok in ["pip", "pip3"]):
        # Look for packages after 'install' or 'download'
        try:
            subcmd_idx = -1
            for idx, t in enumerate(tokens):
                if t.lower() in ("install", "download"):
                    subcmd_idx = idx
                    break
            if subcmd_idx != -1:
                for pkg in tokens[subcmd_idx + 1:]:
                    clean_name = re.split(r"[><=~!;@]", pkg)[0].strip()
                    if clean_name and not clean_name.startswith("-") and not clean_name.endswith(".txt"):
                        results.append(("pypi", clean_name))
        except Exception:
            pass

    elif any(tok in lowered for tok in ["npm", "yarn", "pnpm"]):
        try:
            subcmd_idx = -1
            for idx, t in enumerate(tokens):
                if t.lower() in ("install", "i", "add"):
                    subcmd_idx = idx
                    break
            if subcmd_idx != -1:
                for pkg in tokens[subcmd_idx + 1:]:
                    clean_name = re.split(r"[@]", pkg.lstrip("@"))[0].strip()
                    if clean_name and not clean_name.startswith("-") and not clean_name.endswith(".json"):
                        results.append(("npm", clean_name))
        except Exception:
            pass

    return results


def check_typosquatting(pkg_name: str, ecosystem: str) -> Optional[str]:
    """Detects if a package name is deceptively close to an authoritative popular package."""
    popular = POPULAR_PYPI_PACKAGES if ecosystem == "pypi" else POPULAR_NPM_PACKAGES
    clean_p = pkg_name.lower().replace("-", "").replace("_", "")

    for pop in popular:
        clean_pop = pop.lower().replace("-", "").replace("_", "")
        if clean_p == clean_pop:
            continue

        ratio = difflib.SequenceMatcher(None, clean_p, clean_pop).ratio()
        if ratio >= 0.82 and len(pkg_name) >= 4:
            return pop

    return None


def verify_package(package_name: str, ecosystem: str = "pypi") -> Dict[str, Any]:
    """
    Performs live pre-flight reputation and typo-squatting inspection against PyPI/npm.
    Returns structured audit data with security badges and warnings.
    """
    clean_name = package_name.strip()
    cache_key = f"{ecosystem}:{clean_name.lower()}"

    if cache_key in _PACKAGE_VERIFIER_CACHE:
        cached_entry = _PACKAGE_VERIFIER_CACHE[cache_key]
        if time.time() - cached_entry.get("_cached_at", 0) < CACHE_EXPIRY_SEC:
            return cached_entry

    typo_target = check_typosquatting(clean_name, ecosystem)
    typo_warning = f"Possible typo-squatting of authoritative package '{typo_target}'!" if typo_target else None

    # Default fallback audit record
    audit_res = {
        "package": clean_name,
        "ecosystem": ecosystem,
        "exists_in_registry": False,
        "age_days": None,
        "version": None,
        "summary": None,
        "is_new": False,
        "typo_warning": typo_warning,
        "badge": "Unverified",
        "risk_level": "medium",
        "verified_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "_cached_at": time.time()
    }

    headers = {"User-Agent": "AITrainer-SecurityGate/2.0"}

    # =========================================================================
    # A. PyPI REGISTRY INSPECTION
    # =========================================================================
    if ecosystem == "pypi":
        url = f"https://pypi.org/pypi/{clean_name}/json"
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=1.8) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8", errors="ignore"))
                    info = data.get("info", {})
                    urls = data.get("urls", [])

                    audit_res["exists_in_registry"] = True
                    audit_res["version"] = info.get("version", "unknown")
                    audit_res["summary"] = (info.get("summary") or "")[:120]

                    # Estimate package age from releases or upload time
                    releases = data.get("releases", {})
                    all_uploads = []
                    for rel_files in releases.values():
                        for f_info in rel_files:
                            upload_t = f_info.get("upload_time")
                            if upload_t:
                                all_uploads.append(upload_t)

                    if all_uploads:
                        all_uploads.sort()
                        first_upload_str = all_uploads[0].split("T")[0]
                        try:
                            upload_epoch = time.mktime(time.strptime(first_upload_str, "%Y-%m-%d"))
                            age_days = max(0, int((time.time() - upload_epoch) / 86400))
                            audit_res["age_days"] = age_days
                            audit_res["is_new"] = age_days < 30
                        except Exception:
                            pass

                    # Compute Badge and Risk
                    if typo_warning:
                        audit_res["badge"] = "⚠️ Typo-Squat Warning"
                        audit_res["risk_level"] = "critical"
                    elif audit_res["is_new"]:
                        audit_res["badge"] = f"⚠️ New Package ({audit_res['age_days']}d old)"
                        audit_res["risk_level"] = "high"
                    else:
                        audit_res["badge"] = f"✓ PyPI Verified (v{audit_res['version']})"
                        audit_res["risk_level"] = "low"

        except urllib.error.HTTPError as he:
            if he.code == 404:
                audit_res["exists_in_registry"] = False
                audit_res["badge"] = "⚠️ Not Found on PyPI"
                audit_res["risk_level"] = "high"
                audit_res["typo_warning"] = typo_warning or "Package does NOT exist on official PyPI. Possible hallucination or private repository."
        except Exception as e:
            audit_res["badge"] = "PyPI Offline / Unreachable"
            audit_res["risk_level"] = "medium"

    # =========================================================================
    # B. npm REGISTRY INSPECTION
    # =========================================================================
    elif ecosystem == "npm":
        url = f"https://registry.npmjs.org/{clean_name}"
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=1.8) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8", errors="ignore"))
                    dist_tags = data.get("dist-tags", {})
                    latest_v = dist_tags.get("latest", "unknown")
                    time_dict = data.get("time", {})
                    created_str = time_dict.get("created", "")

                    audit_res["exists_in_registry"] = True
                    audit_res["version"] = latest_v
                    audit_res["summary"] = (data.get("description") or "")[:120]

                    if created_str:
                        try:
                            created_date = created_str.split("T")[0]
                            created_epoch = time.mktime(time.strptime(created_date, "%Y-%m-%d"))
                            age_days = max(0, int((time.time() - created_epoch) / 86400))
                            audit_res["age_days"] = age_days
                            audit_res["is_new"] = age_days < 30
                        except Exception:
                            pass

                    if typo_warning:
                        audit_res["badge"] = "⚠️ Typo-Squat Warning"
                        audit_res["risk_level"] = "critical"
                    elif audit_res["is_new"]:
                        audit_res["badge"] = f"⚠️ New Package ({audit_res['age_days']}d old)"
                        audit_res["risk_level"] = "high"
                    else:
                        audit_res["badge"] = f"✓ npm Verified (v{audit_res['version']})"
                        audit_res["risk_level"] = "low"

        except urllib.error.HTTPError as he:
            if he.code == 404:
                audit_res["exists_in_registry"] = False
                audit_res["badge"] = "⚠️ Not Found on npm"
                audit_res["risk_level"] = "high"
                audit_res["typo_warning"] = typo_warning or "Package does NOT exist on official npm. Possible hallucination."
        except Exception:
            audit_res["badge"] = "npm Offline / Unreachable"
            audit_res["risk_level"] = "medium"

    _PACKAGE_VERIFIER_CACHE[cache_key] = audit_res
    return audit_res


def audit_command_packages(command: str) -> List[Dict[str, Any]]:
    """Inspects all packages inside an install command and returns their pre-flight audit report."""
    extracted = extract_package_names(command)
    audits = []
    for eco, pkg in extracted:
        audits.append(verify_package(pkg, eco))
    return audits
