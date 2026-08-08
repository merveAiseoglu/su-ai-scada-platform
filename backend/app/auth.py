import os
from datetime import datetime, timedelta
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app import models, schemas
from app.database import get_db

SECRET_KEY = os.getenv("SECRET_KEY", "gizli_ve_uzun_bir_anahtar_su_ai")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 1 hafta

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)) -> models.Kullanici:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Kimlik doğrulama başarısız",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = schemas.TokenData(email=email, rol=payload.get("rol"))
    except jwt.PyJWTError as err:
        raise credentials_exception from err

    result = await db.execute(select(models.Kullanici).filter(models.Kullanici.email == token_data.email))
    user = result.scalars().first()
    if user is None or not user.aktif_mi:
        raise credentials_exception
    return user


def require_role(allowed_roles: list[str]):
    """
    Kullanıcının belirtilen rollerden birine sahip olup olmadığını kontrol eden FastAPI Dependency'si.
    Kullanım: current_user = Depends(require_role(["saha_personeli", "yonetici"]))
    """

    async def role_checker(current_user: models.Kullanici = Depends(get_current_user)) -> models.Kullanici:
        if current_user.rol not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Bu işlemi yapmak için yetkiniz bulunmamaktadır."
            )
        return current_user

    return role_checker


async def log_audit(db: AsyncSession, kullanici_id: int, islem_tipi: str, detay: str = None):
    """Sistem üzerinde yapılan önemli işlemleri denetim izine (Audit Log) kaydeder."""
    audit = models.AuditLog(kullanici_id=kullanici_id, islem_tipi=islem_tipi, detay=detay)
    db.add(audit)
    await db.commit()
