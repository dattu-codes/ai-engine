from typing import Optional
from cryptography.fernet import Fernet
from app.config import settings

def get_fernet() -> Fernet:
    key = settings.TOKEN_ENCRYPTION_KEY
    if not key:
        raise ValueError("TOKEN_ENCRYPTION_KEY is not configured")
    if isinstance(key, str):
        key = key.encode("utf-8")
    return Fernet(key)

def encrypt_token(plain_token: Optional[str]) -> Optional[str]:
    """Encrypt a plaintext token using Fernet. Returns base64 ciphertext string."""
    if not plain_token:
        return None
    f = get_fernet()
    encrypted = f.encrypt(plain_token.encode("utf-8"))
    return encrypted.decode("utf-8")

class GitHubTokenDecryptionError(Exception):
    """Raised when decrypting a stored GitHub token fails (e.g. invalid key, corrupted data, or unencrypted plaintext)."""
    pass

def decrypt_token(encrypted_token: Optional[str]) -> Optional[str]:
    """Decrypt a Fernet-encrypted token string. Raises GitHubTokenDecryptionError on failure."""
    if not encrypted_token:
        return None
    try:
        f = get_fernet()
        decrypted = f.decrypt(encrypted_token.encode("utf-8"))
        return decrypted.decode("utf-8")
    except Exception as e:
        raise GitHubTokenDecryptionError("Unable to decrypt GitHub token. Please reconnect your GitHub account.") from e
