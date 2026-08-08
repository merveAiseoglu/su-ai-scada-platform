import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

# GELİŞTİRME ORTAMI: Şema değişikliklerini uygulamak için tabloları yeniden oluştur.
# ÜRETİMDE bu satırı False yapın veya Alembic migration'a geçin.
DEV_DROP_RECREATE = os.getenv("DEV_DROP_RECREATE", "true").lower() == "true"

engine = create_async_engine(DATABASE_URL)
SessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

async def get_db():
    async with SessionLocal() as db:
        yield db