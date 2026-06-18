"""
AES-256-GCM authenticated encryption for sensitive fields.

Algorithm : AES (Advanced Encryption Standard)
Key size  : 256 bits (32 bytes)
Mode      : GCM (Galois/Counter Mode) — provides confidentiality + integrity in one pass

Wire format: base64url( nonce[12] || ciphertext_with_tag[n+16] )

Activation : ONLY when ENCRYPTION_KEY is set in the environment.
             In local / dev environments (no ENCRYPTION_KEY), the class operates in
             passthrough mode — encrypt/decrypt return the value unchanged.
"""
import os
import base64
import logging
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings

logger = logging.getLogger(__name__)

_NONCE_SIZE = 12   # 96-bit nonce — GCM recommended length
_KEY_SIZE   = 32   # 256-bit key — AES-256


class HybridEncryption:
    """
    AES-256-GCM encryption for sensitive data fields.

    Enabled  : ENCRYPTION_KEY env var is set (production only).
    Disabled : ENCRYPTION_KEY is absent — encrypt/decrypt are no-ops (plaintext passthrough).
    """

    def __init__(self, encryption_key: Optional[str]):
        if encryption_key:
            raw = base64.urlsafe_b64decode(encryption_key + "==")
            if len(raw) != _KEY_SIZE:
                raise ValueError(
                    f"ENCRYPTION_KEY must decode to {_KEY_SIZE} bytes, got {len(raw)}"
                )
            self._aesgcm = AESGCM(raw)
            self._enabled = True
            logger.info("AES-256-GCM encryption: ENABLED (production key loaded)")
        else:
            self._aesgcm = None
            self._enabled = False
            logger.info("AES-256-GCM encryption: DISABLED (no ENCRYPTION_KEY set — plaintext passthrough)")

    @property
    def enabled(self) -> bool:
        return self._enabled

    def encrypt_sensitive_field(self, value: str) -> str:
        """
        Encrypt a plaintext string.

        Returns base64url(nonce || ciphertext_with_tag) when enabled.
        Returns the original value unchanged when encryption is disabled.
        """
        if not value or not self._enabled:
            return value
        try:
            nonce = os.urandom(_NONCE_SIZE)
            ct    = self._aesgcm.encrypt(nonce, value.encode(), None)
            return base64.urlsafe_b64encode(nonce + ct).decode()
        except Exception as e:
            logger.error("AES-256-GCM encryption failed")
            raise ValueError("Failed to encrypt field") from e

    def decrypt_sensitive_field(self, token: str) -> str:
        """
        Decrypt a base64url(nonce || ciphertext_with_tag) token.

        GCM authentication tag is verified automatically; raises ValueError
        on any tampering or wrong key.
        Returns the original value unchanged when encryption is disabled.
        """
        if not token or not self._enabled:
            return token
        try:
            raw       = base64.urlsafe_b64decode(token + "==")
            nonce, ct = raw[:_NONCE_SIZE], raw[_NONCE_SIZE:]
            return self._aesgcm.decrypt(nonce, ct, None).decode()
        except Exception as e:
            logger.error("AES-256-GCM decryption failed")
            raise ValueError("Failed to decrypt field") from e


# Global singleton — used across the application.
# Enabled only when ENCRYPTION_KEY is present in the environment (production).
hybrid_encryption = HybridEncryption(encryption_key=settings.ENCRYPTION_KEY)
