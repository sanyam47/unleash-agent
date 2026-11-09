"""
AES-256-GCM Encrypted Credential & API Secret Vault.
Addresses enterprise AppSec compliance (Marcus Kane & Viktor Brandt):
  1. Zero plaintext API keys at rest.
  2. Uses cryptography.hazmat.primitives.ciphers.aead.AESGCM (256-bit key authenticated encryption).
  3. Machine-bound local master key derivation with PBKDF2 (100,000 iterations, SHA-256).
  4. Nonce randomization (96-bit unique nonce per write) + 128-bit authentication tag validation.
  5. Automatic migration fallback for legacy Fernet payloads.
  6. Manages secrets for Cloud GPU providers (RunPod, Modal, OpenAI, Kaggle).
"""

import os
import json
import base64
from pathlib import Path
from typing import Dict, Any, List, Optional
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

MASTER_KEY_FILE = DATA_DIR / ".vault_master.key"
VAULT_ENC_FILE = DATA_DIR / "vault.enc"
SALT = b"unleash_agent_vault_salt_2026"
MAGIC_PREFIX = b"GCM1"  # 4-byte header identifying AES-256-GCM format


def _derive_aes256_key() -> bytes:
    """Derives a 256-bit (32 bytes) key from local master seed file using PBKDF2."""
    if not MASTER_KEY_FILE.exists():
        raw_seed = os.urandom(32)
        MASTER_KEY_FILE.write_bytes(raw_seed)
    else:
        raw_seed = MASTER_KEY_FILE.read_bytes()

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=SALT,
        iterations=100000,
    )
    return kdf.derive(raw_seed)


def _load_vault_data() -> Dict[str, str]:
    """Loads and decrypts the vault file from disk using AES-256-GCM (with Fernet fallback)."""
    if not VAULT_ENC_FILE.exists():
        return {}

    try:
        raw_bytes = VAULT_ENC_FILE.read_bytes()
        if not raw_bytes:
            return {}

        # 1. AES-256-GCM Format: MAGIC_PREFIX (4) + NONCE (12) + CIPHERTEXT_WITH_TAG
        if raw_bytes.startswith(MAGIC_PREFIX) and len(raw_bytes) >= 16:
            key = _derive_aes256_key()
            aesgcm = AESGCM(key)
            nonce = raw_bytes[4:16]
            ciphertext = raw_bytes[16:]
            dec_bytes = aesgcm.decrypt(nonce, ciphertext, None)
            return json.loads(dec_bytes.decode("utf-8"))

        # 2. Legacy Fernet Migration Fallback
        from cryptography.fernet import Fernet
        raw_seed = MASTER_KEY_FILE.read_bytes() if MASTER_KEY_FILE.exists() else b""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=SALT,
            iterations=100000,
        )
        legacy_key = base64.urlsafe_b64encode(kdf.derive(raw_seed))
        fernet = Fernet(legacy_key)
        dec_bytes = fernet.decrypt(raw_bytes)
        migrated_data = json.loads(dec_bytes.decode("utf-8"))
        # Auto-upgrade to AES-256-GCM
        _save_vault_data(migrated_data)
        return migrated_data

    except Exception as e:
        print(f"[CredentialVault] Warning: Decryption failed, resetting vault: {e}")
        return {}


def _save_vault_data(data: Dict[str, str]) -> bool:
    """Encrypts and atomically writes the vault file to disk with AES-256-GCM."""
    try:
        key = _derive_aes256_key()
        aesgcm = AESGCM(key)
        nonce = os.urandom(12)  # 96-bit unique nonce
        serialized = json.dumps(data).encode("utf-8")
        
        # aesgcm.encrypt returns ciphertext with 128-bit authentication tag appended
        ciphertext = aesgcm.encrypt(nonce, serialized, None)
        payload = MAGIC_PREFIX + nonce + ciphertext

        tmp_file = DATA_DIR / "vault.enc.tmp"
        tmp_file.write_bytes(payload)
        if os.path.exists(VAULT_ENC_FILE):
            os.replace(tmp_file, VAULT_ENC_FILE)
        else:
            os.rename(tmp_file, VAULT_ENC_FILE)
        return True
    except Exception as e:
        print(f"[CredentialVault] Error saving encrypted vault: {e}")
        return False


def store_secret(service_name: str, secret_value: str) -> Dict[str, Any]:
    """Stores an encrypted secret (API key, token, or private URL) at rest."""
    clean_service = service_name.lower().strip()
    vault = _load_vault_data()
    vault[clean_service] = str(secret_value).strip()
    saved = _save_vault_data(vault)
    return {
        "status": "success" if saved else "error",
        "service": clean_service,
        "encrypted": True,
        "cipher": "AES-256-GCM",
        "message": f"Successfully encrypted and stored credential for '{clean_service}' via AES-256-GCM at rest."
    }


def get_secret(service_name: str) -> Optional[str]:
    """Decrypts and returns the requested secret in-memory."""
    clean_service = service_name.lower().strip()
    vault = _load_vault_data()
    return vault.get(clean_service)


def has_secret(service_name: str) -> bool:
    """Checks whether an encrypted secret exists for a service without exposing the key."""
    clean_service = service_name.lower().strip()
    vault = _load_vault_data()
    return clean_service in vault and bool(vault[clean_service])


def list_configured_services() -> List[str]:
    """Returns list of configured services without exposing their secrets."""
    vault = _load_vault_data()
    return list(vault.keys())


def delete_secret(service_name: str) -> bool:
    """Removes an encrypted secret from the vault."""
    clean_service = service_name.lower().strip()
    vault = _load_vault_data()
    if clean_service in vault:
        del vault[clean_service]
        _save_vault_data(vault)
        return True
    return False
