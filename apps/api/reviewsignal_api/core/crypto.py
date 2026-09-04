"""Encryption for runtime-issued secrets held in PostgreSQL.

`docs/deployment.md` §10 keeps OAuth tokens out of source control and
`docs/data-model.md` §17 keeps them out of `settings`. A refresh token is issued at
runtime by the OAuth callback, so it cannot be an environment variable either: those
are fixed at deploy time. It is encrypted here and stored as ciphertext in
`source_credentials`.
"""

from functools import lru_cache

from cryptography.fernet import Fernet

from reviewsignal_api.core.config import get_settings


class EncryptionKeyMissingError(RuntimeError):
    """Raised when a credential operation is attempted without a configured key."""


@lru_cache
def _cipher() -> Fernet:
    key = get_settings().credential_encryption_key
    if not key:
        raise EncryptionKeyMissingError(
            "CREDENTIAL_ENCRYPTION_KEY is not set; OAuth tokens cannot be stored or read."
        )
    return Fernet(key.encode())


def encrypt(plaintext: str) -> bytes:
    return _cipher().encrypt(plaintext.encode())


def decrypt(ciphertext: bytes) -> str:
    return _cipher().decrypt(ciphertext).decode()
