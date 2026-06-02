"""
WikiMe Security Middleware — AES-256-GCM encryption for wiki vault files.

Encrypts page content before writing to disk. Decrypts on read.
The master key is stored in ~/.hermes/plugins/wikime/secret/vault.key.

Usage:
    from src.security import WikiSecurityManager
    sec = WikiSecurityManager()
    encrypted = sec.encrypt_text("sensitive content")
    plain = sec.decrypt_text(encrypted)
"""

from __future__ import annotations

import base64
import logging
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger(__name__)

_KEY_DIR = os.path.expanduser("~/.hermes/plugins/wikime/secret")
_KEY_FILE = os.path.join(_KEY_DIR, "vault.key")
_KEY_SIZE = 32  # 256 bits
_NONCE_SIZE = 12  # 96 bits for GCM


class WikiSecurityManager:
    """Encrypt and decrypt wiki page content using AES-256-GCM."""

    def __init__(self, key_dir: str = _KEY_DIR):
        self.key_path = os.path.join(os.path.expanduser(key_dir), "vault.key")
        os.makedirs(os.path.dirname(self.key_path), exist_ok=True)
        self._key = self._load_or_create_key()

    # -- public API ---------------------------------------------------------

    def encrypt(self, plain_text: str) -> str:
        """Encrypt a string, returning base64-encoded ciphertext."""
        if not plain_text:
            return plain_text
        aesgcm = AESGCM(self._key)
        nonce = os.urandom(_NONCE_SIZE)
        ct = aesgcm.encrypt(nonce, plain_text.encode("utf-8"), None)
        return base64.b64encode(nonce + ct).decode("ascii")

    def decrypt(self, b64_text: str) -> str:
        """Decrypt a base64-encoded ciphertext back to plain text.
        If the input is not valid encrypted data, returns it unchanged."""
        if not b64_text:
            return b64_text
        try:
            raw = base64.b64decode(b64_text.encode("ascii"))
            nonce = raw[:_NONCE_SIZE]
            ct = raw[_NONCE_SIZE:]
            aesgcm = AESGCM(self._key)
            pt = aesgcm.decrypt(nonce, ct, None)
            return pt.decode("utf-8")
        except Exception:
            # Not encrypted — return as-is (for reading unencrypted legacy files)
            return b64_text

    def rotate_key(self) -> None:
        """Generate a new encryption key. Existing encrypted files will need
        re-encryption with decrypt-then-encrypt."""
        self._key = AESGCM.generate_key(bit_length=256)
        with open(self.key_path, "wb") as f:
            f.write(self._key)
        logger.info("[WikiMe Security] Encryption key rotated.")

    # -- internal -----------------------------------------------------------

    def _load_or_create_key(self) -> bytes:
        if os.path.exists(self.key_path):
            with open(self.key_path, "rb") as f:
                key = f.read()
            if len(key) == _KEY_SIZE:
                return key
            logger.warning("[WikiMe Security] Existing key has wrong size, regenerating.")

        key = AESGCM.generate_key(bit_length=256)
        with open(self.key_path, "wb") as f:
            f.write(key)
        # Restrict permissions to owner only
        os.chmod(self.key_path, 0o600)
        logger.info("[WikiMe Security] Generated new AES-256-GCM key.")
        return key
