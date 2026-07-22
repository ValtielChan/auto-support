"""Symmetric encryption for stored credentials (IMAP/SMTP passwords, API keys).

The Fernet key is derived from SECRET_KEY, so changing SECRET_KEY invalidates
stored credentials - they would need to be re-entered.
"""

import base64
import hashlib

from cryptography.fernet import Fernet

from ..config import settings


def _fernet() -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(settings.secret_key.encode()).digest())
    return Fernet(key)


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    return _fernet().decrypt(value.encode()).decode()
