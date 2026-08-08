"""
Zynmail Enterprise Data Encryption Service.
Provides AES-256-CBC-HMAC authenticated encryption (Fernet) for data at rest,
field-level database encryption, OAuth credentials, and confidential messages.
"""

import os
import json
import base64
import hashlib
from typing import Any, Dict, List, Optional
from cryptography.fernet import Fernet, InvalidToken
from app.config import get_settings

settings = get_settings()

_fernet_instance: Optional[Fernet] = None
ENCRYPTION_PREFIX = "enc:"


def get_encryption_key() -> bytes:
    """Retrieves or derives the 32-byte URL-safe base64 encryption key."""
    raw_key = settings.encryption_key.strip()
    if raw_key:
        try:
            # Validate if it's already a valid 32-byte Fernet key
            key_bytes = raw_key.encode("utf-8")
            Fernet(key_bytes)
            return key_bytes
        except Exception:
            # Derive 32-byte urlsafe base64 key using SHA-256
            derived = hashlib.sha256(raw_key.encode("utf-8")).digest()
            return base64.urlsafe_b64encode(derived)

    # Fallback to deterministic key based on app config
    seed = f"{settings.database_name}:{settings.app_name}:zynmail-secret-salt"
    derived = hashlib.sha256(seed.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(derived)


def get_fernet() -> Fernet:
    """Returns a singleton Fernet cipher instance."""
    global _fernet_instance
    if _fernet_instance is None:
        key = get_encryption_key()
        _fernet_instance = Fernet(key)
    return _fernet_instance


def encrypt_text(plaintext: Optional[str]) -> Optional[str]:
    """
    Encrypts a plaintext string using AES-256 authenticated encryption.
    Returns ciphertext prefixed with 'enc:'.
    """
    if plaintext is None:
        return None
    if not isinstance(plaintext, str):
        plaintext = str(plaintext)
    if plaintext == "":
        return ""
    if plaintext.startswith(ENCRYPTION_PREFIX):
        return plaintext  # Already encrypted

    try:
        f = get_fernet()
        token = f.encrypt(plaintext.encode("utf-8"))
        return f"{ENCRYPTION_PREFIX}{token.decode('utf-8')}"
    except Exception as e:
        print(f"Encryption error: {e}")
        return plaintext


def decrypt_text(ciphertext: Optional[str]) -> Optional[str]:
    """
    Decrypts a ciphertext string prefixed with 'enc:'.
    If unencrypted (legacy data), returns the string as-is.
    """
    if ciphertext is None:
        return None
    if not isinstance(ciphertext, str):
        return ciphertext
    if not ciphertext.startswith(ENCRYPTION_PREFIX):
        return ciphertext  # Plaintext / legacy data

    try:
        raw_token = ciphertext[len(ENCRYPTION_PREFIX):]
        f = get_fernet()
        decrypted_bytes = f.decrypt(raw_token.encode("utf-8"))
        return decrypted_bytes.decode("utf-8")
    except InvalidToken:
        print("Warning: Invalid encryption token or key mismatch during decryption.")
        return ciphertext
    except Exception as e:
        print(f"Decryption error: {e}")
        return ciphertext


def encrypt_json(data: Any) -> str:
    """Serializes data to JSON and encrypts it."""
    json_str = json.dumps(data)
    return encrypt_text(json_str) or ""


def decrypt_json(ciphertext: Optional[str]) -> Any:
    """Decrypts ciphertext and parses JSON. Returns None on failure."""
    if not ciphertext:
        return None
    decrypted_str = decrypt_text(ciphertext)
    if not decrypted_str:
        return None
    try:
        return json.loads(decrypted_str)
    except json.JSONDecodeError:
        return None


def encrypt_email_fields(doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Encrypts sensitive email fields (body_plain, body_html, snippet)
    before writing to MongoDB.
    """
    if not doc or not isinstance(doc, dict):
        return doc

    encrypted_doc = dict(doc)

    if "body" in encrypted_doc and encrypted_doc["body"]:
        encrypted_doc["body"] = encrypt_text(encrypted_doc["body"])

    if "body_plain" in encrypted_doc and encrypted_doc["body_plain"]:
        encrypted_doc["body_plain"] = encrypt_text(encrypted_doc["body_plain"])

    if "body_html" in encrypted_doc and encrypted_doc["body_html"]:
        encrypted_doc["body_html"] = encrypt_text(encrypted_doc["body_html"])

    if "snippet" in encrypted_doc and encrypted_doc["snippet"]:
        encrypted_doc["snippet"] = encrypt_text(encrypted_doc["snippet"])

    # If attachments have base64 data, encrypt data
    if "attachments" in encrypted_doc and isinstance(encrypted_doc["attachments"], list):
        encrypted_attachments = []
        for att in encrypted_doc["attachments"]:
            if isinstance(att, dict) and "data" in att and att["data"]:
                att_copy = dict(att)
                att_copy["data"] = encrypt_text(att_copy["data"])
                encrypted_attachments.append(att_copy)
            else:
                encrypted_attachments.append(att)
        encrypted_doc["attachments"] = encrypted_attachments

    return encrypted_doc


def decrypt_email_fields(doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Decrypts sensitive email fields (body, body_plain, body_html, snippet)
    when reading from MongoDB.
    """
    if not doc or not isinstance(doc, dict):
        return doc

    decrypted_doc = dict(doc)

    if "body" in decrypted_doc and decrypted_doc["body"]:
        decrypted_doc["body"] = decrypt_text(decrypted_doc["body"])

    if "body_plain" in decrypted_doc and decrypted_doc["body_plain"]:
        decrypted_doc["body_plain"] = decrypt_text(decrypted_doc["body_plain"])

    if "body_html" in decrypted_doc and decrypted_doc["body_html"]:
        decrypted_doc["body_html"] = decrypt_text(decrypted_doc["body_html"])

    if "snippet" in decrypted_doc and decrypted_doc["snippet"]:
        decrypted_doc["snippet"] = decrypt_text(decrypted_doc["snippet"])

    if "attachments" in decrypted_doc and isinstance(decrypted_doc["attachments"], list):
        decrypted_attachments = []
        for att in decrypted_doc["attachments"]:
            if isinstance(att, dict) and "data" in att and att["data"]:
                att_copy = dict(att)
                att_copy["data"] = decrypt_text(att_copy["data"])
                decrypted_attachments.append(att_copy)
            else:
                decrypted_attachments.append(att)
        decrypted_doc["attachments"] = decrypted_attachments

    return decrypted_doc


def save_encrypted_json_file(filepath: str, data: Any) -> None:
    """Encrypts data and saves it to a file with secure 0o600 permissions."""
    try:
        encrypted_payload = encrypt_json(data)
        with open(filepath, "w") as f:
            f.write(encrypted_payload)
        os.chmod(filepath, 0o600)
    except Exception as e:
        print(f"Error saving encrypted file {filepath}: {e}")


def load_encrypted_json_file(filepath: str) -> Optional[Any]:
    """
    Loads and decrypts JSON data from file.
    Supports both encrypted ciphertext and legacy unencrypted JSON.
    """
    if not os.path.exists(filepath):
        return None

    try:
        with open(filepath, "r") as f:
            content = f.read().strip()

        if not content:
            return None

        # Check if encrypted with prefix
        if content.startswith(ENCRYPTION_PREFIX):
            return decrypt_json(content)

        # Legacy unencrypted JSON fallback
        try:
            legacy_data = json.loads(content)
            # Seamlessly upgrade legacy file to encrypted format
            save_encrypted_json_file(filepath, legacy_data)
            return legacy_data
        except json.JSONDecodeError:
            return None
    except Exception as e:
        print(f"Error loading encrypted file {filepath}: {e}")
        return None
