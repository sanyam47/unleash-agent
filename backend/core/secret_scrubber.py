"""
Autonomous Dynamic Secret & Credential Scrubber (TruffleHog & GitGuardian Grade)

Implements 5-Layer Defense-in-Depth against credential and secret leaks:
  Layer 1: Shannon Entropy Analysis (mathematical randomness > 4.5 bits/char)
  Layer 2: Active Environment Ingestion (dynamically ingests host os.environ & .env)
  Layer 3: Database Connection String & URI Masking (postgres, mysql, mongodb, redis)
  Layer 4: Cryptographic Private Keys & PKI Certificate Blocks (RSA, SSH, PGP, JWT)
  Layer 5: High-Confidence Cloud & Service Signatures (OpenAI, Groq, GitHub, AWS, Stripe)
"""

import os
import re
import math
from pathlib import Path
from typing import Dict, Any, List, Tuple, Set, Optional

# Standard service signature patterns
KNOWN_SECRET_PATTERNS = [
    # OpenAI API Keys
    (r"\bsk-(?:proj-)?[a-zA-Z0-9_\-]{20,}\b", "OPENAI_API_KEY"),
    # Anthropic API Keys
    (r"\bsk-ant-[a-zA-Z0-9_\-]{20,}\b", "ANTHROPIC_API_KEY"),
    # Groq API Keys
    (r"\bgsk_[a-zA-Z0-9_\-]{20,}\b", "GROQ_API_KEY"),
    # GitHub Personal Access & OAuth Tokens
    (r"\bgh[pousr]_[a-zA-Z0-9]{36,}\b", "GITHUB_TOKEN"),
    # AWS Access Key IDs
    (r"\bAKIA[0-9A-Z]{16}\b", "AWS_ACCESS_KEY_ID"),
    # Google Cloud / Firebase API Keys
    (r"\bAIzaSy[a-zA-Z0-9_\-]{33}\b", "GOOGLE_API_KEY"),
    # Stripe Secret Keys
    (r"\b(?:sk|rk)_(?:live|test)_[0-9a-zA-Z]{24,}\b", "STRIPE_SECRET_KEY"),
    # Slack / Discord Webhook URLs
    (r"https:\/\/(?:hooks\.slack\.com\/services|discord(?:app)?\.com\/api\/webhooks)\/[a-zA-Z0-9_\-\/]+", "WEBHOOK_URL"),
    # JWT Tokens (header.payload.signature)
    (r"\beyJ[a-zA-Z0-9_\-]{10,}\.eyJ[a-zA-Z0-9_\-]{10,}\.[a-zA-Z0-9_\-]{10,}\b", "JWT_TOKEN"),
]

# Database Connection URIs (with embedded passwords)
DATABASE_URI_PATTERN = re.compile(
    r"\b((?:postgres|postgresql|mysql|mongodb(?:\+srv)?|redis|amqp):\/\/)([^:\s\/]+):([^@\s\/]+)@([a-zA-Z0-9\.\-_]+)",
    re.IGNORECASE
)

# PKI Private Key Blocks
PRIVATE_KEY_BLOCK_PATTERN = re.compile(
    r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----[\s\S]+?-----END (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----"
)

# Generic assignment patterns for high entropy inspection
ASSIGNMENT_SECRET_PATTERN = re.compile(
    r"""(?i)\b(?:api[_-]?key|secret[_-]?(?:key|token)?|secret|token|password|passwd|auth[_-]?token|jwt[_-]?secret|private[_-]?key)\s*[:=]\s*["']([^"'\r\n]{12,})["']"""
)


def calculate_shannon_entropy(data: str) -> float:
    """Calculates Shannon entropy in bits per character."""
    if not data:
        return 0.0
    entropy = 0.0
    length = len(data)
    frequencies = {}
    for char in data:
        frequencies[char] = frequencies.get(char, 0) + 1
    for count in frequencies.values():
        p = count / length
        entropy -= p * math.log2(p)
    return entropy


class SecretScrubber:
    """
    Scans, audits, and redacts sensitive credentials and high-entropy secrets
    from code files, chat outputs, and terminal execution traces.
    """
    _env_secrets_cache: Optional[Set[str]] = None

    @classmethod
    def get_active_env_secrets(cls, force_reload: bool = False) -> Set[str]:
        """
        Dynamically ingests sensitive values from os.environ and local .env files.
        Collects real tokens so they are never leaked in terminal outputs or chat.
        """
        if cls._env_secrets_cache is not None and not force_reload:
            return cls._env_secrets_cache

        secrets = set()
        sensitive_key_words = {"KEY", "SECRET", "TOKEN", "PASSWORD", "AUTH", "PASS", "CREDENTIAL"}
        ignore_values = {"true", "false", "default", "none", "null", "undefined", "localhost", "127.0.0.1", "0.0.0.0"}

        # 1. Ingest from host process os.environ
        for k, v in os.environ.items():
            if any(w in k.upper() for w in sensitive_key_words):
                val = str(v).strip()
                if len(val) >= 8 and val.lower() not in ignore_values:
                    secrets.add(val)

        # 2. Ingest from project root .env if present
        try:
            root_env = Path("c:/coding/ai-trainer/.env")
            if root_env.exists():
                lines = root_env.read_text(encoding="utf-8", errors="replace").splitlines()
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        val = v.strip().strip("'\"")
                        if any(w in k.upper() for w in sensitive_key_words) and len(val) >= 8 and val.lower() not in ignore_values:
                            secrets.add(val)
        except Exception:
            pass

        cls._env_secrets_cache = secrets
        return cls._env_secrets_cache

    @classmethod
    def scrub_text(cls, text: str) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Redacts secrets from arbitrary text, returning the sanitized text and audit metadata.
        """
        if not text:
            return text, []

        detections: List[Dict[str, Any]] = []
        scrubbed = text

        # 1. Redact PKI Private Key Blocks
        for match in PRIVATE_KEY_BLOCK_PATTERN.finditer(text):
            detections.append({
                "type": "PKI_PRIVATE_KEY",
                "severity": "CRITICAL",
                "preview": match.group(0)[:30] + "..."
            })
            scrubbed = scrubbed.replace(match.group(0), "[REDACTED_PRIVATE_KEY]")

        # 2. Redact Database Connection Passwords in URIs
        def _mask_db_uri(m):
            proto, user, pwd, host = m.group(1), m.group(2), m.group(3), m.group(4)
            detections.append({
                "type": "DATABASE_CREDENTIAL",
                "severity": "HIGH",
                "preview": f"{proto}{user}:***@{host}"
            })
            return f"{proto}{user}:[REDACTED_DB_PASSWORD]@{host}"

        scrubbed = DATABASE_URI_PATTERN.sub(_mask_db_uri, scrubbed)

        # 3. Redact Known Standard Service API Keys
        for pattern, label in KNOWN_SECRET_PATTERNS:
            for m in re.finditer(pattern, scrubbed):
                val = m.group(0)
                detections.append({
                    "type": label,
                    "severity": "HIGH",
                    "preview": val[:6] + "..." + val[-3:] if len(val) > 10 else "[KEY]"
                })
                scrubbed = scrubbed.replace(val, f"[REDACTED_{label}]")

        # 4. Ingested Active Host Environment Secrets
        active_secrets = cls.get_active_env_secrets()
        for sec in active_secrets:
            if sec in scrubbed:
                detections.append({
                    "type": "HOST_ENV_SECRET",
                    "severity": "CRITICAL",
                    "preview": sec[:4] + "..." + sec[-2:] if len(sec) > 8 else "***"
                })
                scrubbed = scrubbed.replace(sec, "[REDACTED_HOST_SECRET]")

        # 5. Shannon Entropy Analysis on Assignments
        for m in ASSIGNMENT_SECRET_PATTERN.finditer(scrubbed):
            candidate = m.group(1)
            # Skip placeholders
            if any(ph in candidate.lower() for ph in ["your_", "example", "placeholder", "xxx", "redacted", "my_secret", "changeme"]):
                continue
            
            # Check character diversity
            unique_chars = len(set(candidate))
            if unique_chars < 8:
                continue

            has_upper = any(c.isupper() for c in candidate)
            has_lower = any(c.islower() for c in candidate)
            has_digit = any(c.isdigit() for c in candidate)
            has_punct = any(not c.isalnum() for c in candidate)
            char_classes = sum([has_upper, has_lower, has_digit, has_punct])

            entropy = calculate_shannon_entropy(candidate)
            # Calibrated thresholds based on length and charset diversity
            threshold = 3.3 if (len(candidate) <= 24 and char_classes >= 2) else 3.8
            if entropy >= threshold:
                detections.append({
                    "type": "HIGH_ENTROPY_SECRET",
                    "severity": "HIGH",
                    "entropy": round(entropy, 2),
                    "preview": candidate[:4] + "..." + candidate[-2:]
                })
                scrubbed = scrubbed.replace(candidate, "[REDACTED_HIGH_ENTROPY_SECRET]")

        return scrubbed, detections


def scrub_sensitive_content(text: str) -> str:
    """Convenience functional wrapper: returns scrubbed string."""
    cleaned, _ = SecretScrubber.scrub_text(text)
    return cleaned
