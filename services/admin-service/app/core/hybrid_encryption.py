"""
Hybrid encryption for sensitive fields
Uses symmetric encryption (Fernet) for data encryption
"""
from cryptography.fernet import Fernet
from typing import Optional
import base64
import hashlib
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class HybridEncryption:
    """Hybrid encryption utility for sensitive data"""
    
    def __init__(self, secret_key: str):
        """
        Initialize encryption with a secret key.
        
        Args:
            secret_key: Secret key for encryption (will be derived into Fernet key)
        """
        # Derive a Fernet key from the secret
        key_bytes = secret_key.encode('utf-8')
        derived_key = hashlib.sha256(key_bytes).digest()
        fernet_key = base64.urlsafe_b64encode(derived_key)
        self.fernet = Fernet(fernet_key)
    
    def encrypt_sensitive_field(self, value: str) -> str:
        """
        Encrypt a sensitive field value.
        
        Args:
            value: Plain text value to encrypt
            
        Returns:
            Encrypted value as base64 string
        """
        try:
            if not value:
                return value
            
            encrypted_bytes = self.fernet.encrypt(value.encode('utf-8'))
            return encrypted_bytes.decode('utf-8')
        except Exception as e:
            logger.error(f"Encryption error: {e}")
            raise ValueError(f"Failed to encrypt field: {e}")
    
    def decrypt_sensitive_field(self, encrypted_value: str) -> str:
        """
        Decrypt a sensitive field value.
        
        Args:
            encrypted_value: Encrypted value as base64 string
            
        Returns:
            Decrypted plain text value
            
        Raises:
            ValueError: If decryption fails
        """
        try:
            if not encrypted_value:
                return encrypted_value
            
            decrypted_bytes = self.fernet.decrypt(encrypted_value.encode('utf-8'))
            return decrypted_bytes.decode('utf-8')
        except Exception as e:
            logger.error(f"Decryption error: {e}")
            raise ValueError(f"Failed to decrypt field: {e}")


# Global encryption instance
hybrid_encryption = HybridEncryption(settings.SECRET_KEY)
