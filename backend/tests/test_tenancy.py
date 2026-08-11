import pytest
import uuid
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Organization, Kullanici, Istasyon, SuOlcumu
from app.auth import get_password_hash, create_access_token

@pytest.fixture
async def multi_tenant_setup(test_db: AsyncSession, seed_users):
    org_a = seed_users["org"]
    admin_a = seed_users["admin"]
    
    # Create Org B
    org_b = Organization(id=uuid.uuid4(), name="Org B")
    test_db.add(org_b)
    await test_db.commit()
    
    # Create Admin for Org B
    admin_b = Kullanici(
        email="admin_b@test.com",
        sifre_hash=get_password_hash("admin123"),
        rol="yonetici",
        aktif_mi=True,
        organization_id=org_b.id
    )
    test_db.add(admin_b)
    await test_db.commit()
    
    # Create Stations
    ist_a = Istasyon(id=101, ad="Station A", tip="Depo", aktif_mi=True, organization_id=org_a.id)
    ist_b = Istasyon(id=102, ad="Station B", tip="Depo", aktif_mi=True, organization_id=org_b.id)
    test_db.add_all([ist_a, ist_b])
    await test_db.commit()

    # Create Measurements
    olcum_a = SuOlcumu(istasyon_id=101, ph=7.1)
    olcum_b = SuOlcumu(istasyon_id=102, ph=7.5)
    test_db.add_all([olcum_a, olcum_b])
    await test_db.commit()

    token_b = create_access_token(data={"sub": admin_b.email, "rol": "yonetici"})
    return {"org_a": org_a, "org_b": org_b, "token_b": token_b}

@pytest.mark.asyncio
async def test_multi_tenancy_isolation(admin_client: AsyncClient, client: AsyncClient, multi_tenant_setup):
    token_b = multi_tenant_setup["token_b"]
    headers_b = {"Authorization": f"Bearer {token_b}"}
    
    # Admin A requests stations, should only see Station A (id=101)
    resp_a = await admin_client.get("/istasyonlar/")
    assert resp_a.status_code == 200
    data_a = resp_a.json()
    assert len(data_a) == 1
    assert data_a[0]["ad"] == "Station A"
    
    # Admin B requests stations, should only see Station B (id=102)
    resp_b = await client.get("/istasyonlar/", headers=headers_b)
    assert resp_b.status_code == 200
    data_b = resp_b.json()
    assert len(data_b) == 1
    assert data_b[0]["ad"] == "Station B"

    # Admin A requests measurements, should only see olcum_a (ph 7.1)
    resp_meas_a = await admin_client.get("/olcumler/")
    assert resp_meas_a.status_code == 200
    meas_a = resp_meas_a.json()
    assert len(meas_a) == 1
    assert meas_a[0]["ph"] == 7.1
    
    # Admin B requests measurements, should only see olcum_b (ph 7.5)
    resp_meas_b = await client.get("/olcumler/", headers=headers_b)
    assert resp_meas_b.status_code == 200
    meas_b = resp_meas_b.json()
    assert len(meas_b) == 1
    assert meas_b[0]["ph"] == 7.5
