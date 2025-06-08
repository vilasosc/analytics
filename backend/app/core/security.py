from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.core.config import settings # Depends on config.py

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

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

# --- Fernet Encryption for Data Source Credentials ---
from cryptography.fernet import Fernet, InvalidToken

def get_fernet_cipher(key: str) -> Fernet:
    # Ensure the key is bytes for Fernet
    key_bytes = key.encode('utf-8')
    # TODO: Consider error handling here if key is not valid Base64, Fernet() will raise error.
    # For now, assume key from settings is correctly formatted.
    return Fernet(key_bytes)

def encrypt_data(plain_text: str, key: str) -> str:
    # 'key' is expected to be the string key from settings.DATASOURCE_ENCRYPTION_KEY
    cipher = get_fernet_cipher(key)
    encrypted_data_bytes = cipher.encrypt(plain_text.encode('utf-8'))
    return encrypted_data_bytes.decode('utf-8') # Store as string

def decrypt_data(encrypted_text: str, key: str) -> str | None:
    # 'key' is expected to be the string key from settings.DATASOURCE_ENCRYPTION_KEY
    cipher = get_fernet_cipher(key)
    try:
        decrypted_data_bytes = cipher.decrypt(encrypted_text.encode('utf-8'))
        return decrypted_data_bytes.decode('utf-8')
    except InvalidToken:
        # In a real app, log this critical security event via logging module
        # For now, printing a warning or returning None is acceptable for the subtask
        # Consider raising a custom exception if specific error handling is needed upstream
        print(f"WARNING: Failed to decrypt data. Token may be invalid or incorrect key used.")
        # Optionally, log the specific error or part of the token for diagnostics if safe
        return None
    except Exception as e:
        # Catch other potential errors during decryption (e.g., if encrypted_text is not valid base64)
        print(f"ERROR: An unexpected error occurred during decryption: {e}")
        return None
