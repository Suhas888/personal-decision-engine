import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from ..config import settings

def _get_fernet() -> Fernet:
    """
    Initialize a Fernet symmetric encryption instance using the ENCRYPTION_KEY.
    In production, ENCRYPTION_KEY must be a secure, base64-encoded 32-byte key.
    If the provided key is not exactly 32 url-safe base64-encoded bytes, we pad/hash it 
    to create a valid Fernet key (useful for local dev with plain strings).
    """
    key = settings.ENCRYPTION_KEY.encode('utf-8')
    try:
        # Try to use it directly if it's a valid 32-byte base64 string
        return Fernet(key)
    except (ValueError, TypeError):
        # Fallback: Hash the key to create a deterministic valid 32-byte Fernet key
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'pde-static-salt', # Deterministic salt since we just want to normalize a badly formatted key
            iterations=100000,
        )
        valid_key = base64.urlsafe_b64encode(kdf.derive(key))
        return Fernet(valid_key)

def encrypt_string(data: str) -> str:
    """Encrypts a string and returns the url-safe base64-encoded string."""
    f = _get_fernet()
    return f.encrypt(data.encode('utf-8')).decode('utf-8')

def decrypt_string(encrypted_data: str) -> str:
    """Decrypts a url-safe base64-encoded string."""
    f = _get_fernet()
    return f.decrypt(encrypted_data.encode('utf-8')).decode('utf-8')
