import json
from typing import Any, Dict, Optional
from cryptography.fernet import Fernet
import structlog

from app.core.config import settings

logger = structlog.get_logger()


class EncryptionError(Exception):
    """Custom exception raised when cryptographic operations fail validation or execution."""
    pass


class SymmetricCrypto:
    """
    Symmetric encryption controller utilizing AES-128/256 via the Cryptography Fernet recipe.
    Handles reversible, high-security sealing of sensitive vendor access credentials,
    secrets, and custom parameter payloads before database ingestion.
    """
    
    # Initialize the engine suite globally using the validated URL-safe base64 master key
    try:
        _cipher = Fernet(settings.ENCRYPTION_SECRET_KEY.encode())
    except Exception as err:
        _cipher = None
        # Centralized critical alert logging for infrastructure monitoring visibility
        logger.critical(
            "Failed to initialize Fernet suite using provided ENCRYPTION_SECRET_KEY token!",
            error=str(err)
        )

    @classmethod
    def _get_cipher(cls) -> Fernet:
        """Internal helper validating active cipher lifecycle state before execution."""
        if not cls._cipher:
            raise EncryptionError(
                "Cryptographic runtime engine is uninitialized. Verify that "
                "ENCRYPTION_SECRET_KEY is configured correctly in your environment variables."
            )
        return cls._cipher

    @classmethod
    def encrypt_string(cls, plaintext: Optional[str]) -> Optional[str]:
        """
        Transforms a raw plaintext sequence into a secure, encrypted Fernet token string.
        Returns None gracefully if given an empty or null input payload.
        """
        if not plaintext:
            return None
            
        try:
            cipher = cls._get_cipher()
            encrypted_bytes = cipher.encrypt(plaintext.encode("utf-8"))
            return encrypted_bytes.decode("utf-8")
        except Exception as err:
            logger.error("Symmetric string encryption operation failure", error=str(err))
            raise EncryptionError("Failed to securely seal raw credential input text string.") from err

    @classmethod
    def decrypt_string(cls, ciphertext: Optional[str]) -> Optional[str]:
        """
        Decrypts an encrypted Fernet token string back to its original raw utf-8 text representation.
        """
        if not ciphertext:
            return None
            
        try:
            cipher = cls._get_cipher()
            decrypted_bytes = cipher.decrypt(ciphertext.encode("utf-8"))
            return decrypted_bytes.decode("utf-8")
        except Exception as err:
            logger.error("Symmetric string decryption operation failure", error=str(err))
            raise EncryptionError("Failed to re-hydrate encrypted credential source payload.") from err

    @classmethod
    def encrypt_json(cls, data: Optional[Dict[str, Any]]) -> Optional[str]:
        """
        Serializes and encrypts a structural key-value dictionary (e.g., extra_params).
        Outputs a single encrypted Fernet token string safe for relational persistence layout storage.
        """
        if data is None:
            return None
            
        try:
            json_str = json.dumps(data, sort_keys=True)
            return cls.encrypt_string(json_str)
        except Exception as err:
            logger.error("Symmetric structural JSON encryption operation failure", error=str(err))
            raise EncryptionError("Failed to securely convert and encrypt dynamic parameter layout blocks.") from err

    @classmethod
    def decrypt_json(cls, ciphertext: Optional[str]) -> Optional[Dict[str, Any]]:
        """
        Decrypts a token string and de-serializes it back into a standard Python structural dictionary mapping.
        """
        if not ciphertext:
            return None
            
        try:
            json_str = cls.decrypt_string(ciphertext)
            if not json_str:
                return None
            return json.loads(json_str)
        except Exception as err:
            logger.error("Symmetric structural JSON decryption operation failure", error=str(err))
            raise EncryptionError("Failed to reconstruct functional dictionary mappings out of cipher string token.") from err