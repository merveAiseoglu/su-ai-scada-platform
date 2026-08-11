import os

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

# Load .env from the root directory
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", ".env")
load_dotenv(dotenv_path)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

# GELİŞTİRME ORTAMI: Şema değişikliklerini uygulamak için tabloları yeniden oluştur.
# ÜRETİMDE bu satırı False yapın veya Alembic migration'a geçin.
DEV_DROP_RECREATE = os.getenv("DEV_DROP_RECREATE", "false").lower() == "true"

engine_kwargs = {}
if DATABASE_URL.startswith("postgresql"):
    engine_kwargs = {
        "pool_size": 50,
        "max_overflow": 150,
        "pool_timeout": 30,
        "pool_pre_ping": True,
    }

engine = create_async_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = async_sessionmaker(
    autocommit=False, autoflush=False, bind=engine, class_=AsyncSession, expire_on_commit=False
)
Base = declarative_base()


async def get_db():
    async with SessionLocal() as db:
        yield db
