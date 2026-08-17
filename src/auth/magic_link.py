

import hashlib
import secrets

def generate_token() -> str:
    """ 32 raw bytes - URL safe token for the email link. """
    return secrets.token_urlsafe(32)

def hash_token(raw_token: str) -> str:
    """ SHA-256 hash for storage. Raw token is never persisted, only this hash """
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


