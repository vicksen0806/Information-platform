import os
import base64
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import jwt, JWTError
from passlib.context import CryptContext
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ─── Password ───────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# ─── JWT ────────────────────────────────────────────────────────────────────

def create_access_token(subject: Any) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(subject), "exp": expire, "type": "access"}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(subject: Any) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {"sub": str(subject), "exp": expire, "type": "refresh"}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return {}


# ─── AES-256-GCM encryption for LLM API keys ────────────────────────────────

def _get_aes_key() -> bytes:
    key = settings.ENCRYPTION_KEY.encode("utf-8")
    # Pad or truncate to exactly 32 bytes
    return key[:32].ljust(32, b"\x00")


def encrypt_api_key(plaintext: str) -> str:
    key = _get_aes_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.b64encode(nonce + ciphertext).decode("utf-8")


def decrypt_api_key(encrypted: str) -> str:
    key = _get_aes_key()
    aesgcm = AESGCM(key)
    data = base64.b64decode(encrypted.encode("utf-8"))
    nonce, ciphertext = data[:12], data[12:]
    return aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")


def mask_api_key(plaintext: str) -> str:
    """Return a masked version like sk-...xxxx for display."""
    if len(plaintext) <= 8:
        return "****"
    return plaintext[:4] + "..." + plaintext[-4:]
