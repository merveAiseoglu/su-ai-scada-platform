import os
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
import sys
from pathlib import Path

# Fix pythonpath for pytest
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app
from app.database import Base, get_db
from app.auth import get_password_hash, create_access_token
from app.models import Kullanici, Istasyon

# Use in-memory SQLite for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession, expire_on_commit=False)

@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"

@pytest.fixture
async def test_db():
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create test session
    async with TestingSessionLocal() as session:
        yield session
    
    # Drop tables after test
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture
def override_get_db(test_db):
    async def _override_get_db():
        yield test_db
    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.clear()

@pytest.fixture
async def client(override_get_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

@pytest.fixture
async def seed_users(test_db: AsyncSession):
    # Create Admin
    admin = Kullanici(
        email="admin@test.com",
        sifre_hash=get_password_hash("admin123"),
        rol="yonetici",
        aktif_mi=True
    )
    # Create Personel
    personel = Kullanici(
        email="personel@test.com",
        sifre_hash=get_password_hash("pers123"),
        rol="saha_personeli",
        aktif_mi=True
    )
    test_db.add_all([admin, personel])
    await test_db.commit()
    return {"admin": admin, "personel": personel}

@pytest.fixture
def admin_token(seed_users):
    return create_access_token(data={"sub": seed_users["admin"].email, "rol": "yonetici"})

@pytest.fixture
def personel_token(seed_users):
    return create_access_token(data={"sub": seed_users["personel"].email, "rol": "saha_personeli"})

@pytest.fixture
async def admin_client(client, admin_token):
    client.headers.update({"Authorization": f"Bearer {admin_token}"})
    return client

@pytest.fixture
async def personel_client(client, personel_token):
    client.headers.update({"Authorization": f"Bearer {personel_token}"})
    return client
