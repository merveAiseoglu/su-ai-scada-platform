import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool
import sys
from pathlib import Path

# Fix pythonpath for pytest
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app
from app.database import Base, get_db
from app.auth import get_password_hash, create_access_token
from app.models import Kullanici, Istasyon, Organization
import uuid

# Use postgres test database
TEST_DATABASE_URL = "postgresql+asyncpg://postgres:merve-dev-password@postgres:5432/su_ai_test"

engine = create_async_engine(
    TEST_DATABASE_URL,
    poolclass=NullPool
)

@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_db():
    # Setup tables once per session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest_asyncio.fixture
async def test_db():
    # Wrap each test in a transaction and rollback at the end
    async with engine.connect() as conn:
        async with conn.begin() as transaction:
            session = AsyncSession(bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False)
            yield session
            await transaction.rollback()

@pytest.fixture
def override_get_db(test_db):
    async def _override_get_db():
        yield test_db
    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.clear()

@pytest_asyncio.fixture
async def client(override_get_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

@pytest_asyncio.fixture
async def seed_users(test_db: AsyncSession):
    # Create Default Organization
    org = Organization(name="Test Org", id=uuid.uuid4())
    test_db.add(org)
    await test_db.commit()

    # Create Admin
    admin = Kullanici(
        email="admin@test.com",
        sifre_hash=get_password_hash("admin123"),
        rol="yonetici",
        aktif_mi=True,
        organization_id=org.id
    )
    # Create Personel
    personel = Kullanici(
        email="personel@test.com",
        sifre_hash=get_password_hash("pers123"),
        rol="saha_personeli",
        aktif_mi=True,
        organization_id=org.id
    )
    test_db.add_all([admin, personel])
    await test_db.commit()
    return {"admin": admin, "personel": personel, "org": org}

@pytest.fixture
def admin_token(seed_users):
    return create_access_token(data={"sub": seed_users["admin"].email, "rol": "yonetici"})

@pytest.fixture
def personel_token(seed_users):
    return create_access_token(data={"sub": seed_users["personel"].email, "rol": "saha_personeli"})

@pytest_asyncio.fixture
async def admin_client(client, admin_token):
    client.headers.update({"Authorization": f"Bearer {admin_token}"})
    return client

@pytest_asyncio.fixture
async def personel_client(client, personel_token):
    client.headers.update({"Authorization": f"Bearer {personel_token}"})
    return client
