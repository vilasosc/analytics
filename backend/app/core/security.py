from datetime import datetime, timedelta, timezone
from typing import Optional
from cryptography.fernet import Fernet
import base64
import hashlib
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.core.config import settings # Depends on config.py

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# Fernet encryption key derivation
def _get_fernet_key() -> bytes:
    """
    Derives a Fernet key from the SECRET_KEY in settings.
    The key is hashed using SHA-256 and then base64 URL-safe encoded.
    """
    hashed_key = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    return base64.urlsafe_b64encode(hashed_key[:32])

fernet = Fernet(_get_fernet_key())

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        # Ensure ACCESS_TOKEN_EXPIRE_MINUTES is treated as int
        # settings.ACCESS_TOKEN_EXPIRE_MINUTES is already int from pydantic model
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def encrypt_data(data: str) -> str:
    """
    Encrypts a string using Fernet encryption.
    """
    encrypted_bytes = fernet.encrypt(data.encode())
    return encrypted_bytes.decode()


def decrypt_data(encrypted_data: str) -> str:
    """
    Decrypts a string using Fernet encryption.
    """
    decrypted_bytes = fernet.decrypt(encrypted_data.encode())
    return decrypted_bytes.decode()
