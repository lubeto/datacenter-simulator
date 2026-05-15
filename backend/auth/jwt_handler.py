"""
DC Monitoring Simulator - Manejo de JWT
"""
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext

SECRET_KEY = os.getenv("SECRET_KEY", "supersecreta_dc_simulator_2024_cambia_esto")
ALGORITHM  = os.getenv("ALGORITHM", "HS256")
EXPIRE_MIN = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: Dict[str, Any],
                        expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if "sub" in to_encode:
        to_encode["sub"] = str(to_encode["sub"])
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=EXPIRE_MIN))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            options={"verify_sub": False},
        )
        return payload
    except JWTError:
        return None
