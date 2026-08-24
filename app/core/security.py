import secrets
import hashlib
from typing import Tuple

def generate_api_key() -> Tuple[str, str]:
    """
    Generates a plaintext API key and its hash.
    Returns: (plaintext_key, hashed_key)
    """
    # Generate a secure random key
    plaintext = f"rg_{secrets.token_urlsafe(32)}"

    # Hash the key for storage
    # Using SHA-256 for simplicity as this is a token, not a password.
    # In a highly secure prod env, we might use a salt + Argon2.
    hashed = hashlib.sha256(plaintext.encode()).hexdigest()

    return plaintext, hashed

def verify_api_key(plaintext: str, hashed: str) -> bool:
    """Verifies a plaintext key against a stored hash."""
    return hashlib.sha256(plaintext.encode()).hexdigest() == hashed
