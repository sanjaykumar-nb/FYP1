import bcrypt
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID
from jose import jwt, JWTError
from starlette.concurrency import run_in_threadpool
from app.config import get_settings

settings = get_settings()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


# bcrypt is slow on purpose (~0.3 s a call). Called directly in a request handler it
# holds the event loop, so every other request waits behind each sign-in; the load
# test (app.scripts.load_test) measured 10 simultaneous sign-ins taking 4.5 s in series.
# On a worker thread (bcrypt releases the GIL) they run side by side.
async def verify_password_async(plain_password: str, hashed_password: str) -> bool:
    return await run_in_threadpool(verify_password, plain_password, hashed_password)


async def get_password_hash_async(password: str) -> str:
    return await run_in_threadpool(get_password_hash, password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        return None


def get_user_id_from_token(token: str) -> Optional[UUID]:
    payload = decode_token(token)
    if payload and payload.get("type") == "access":
        return UUID(payload.get("sub"))
    return None


def get_org_id_from_token(token: str) -> Optional[UUID]:
    payload = decode_token(token)
    if payload and payload.get("type") == "access":
        return UUID(payload.get("org_id"))
    return None