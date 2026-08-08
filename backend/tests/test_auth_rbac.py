import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_login_flow(client: AsyncClient, seed_users):
    # Test valid login
    response = await client.post(
        "/token",
        data={"username": "admin@test.com", "password": "admin123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    assert response.status_code == 200
    assert "access_token" in response.json()
    
    # Test invalid login
    response_invalid = await client.post(
        "/token",
        data={"username": "admin@test.com", "password": "wrongpassword"},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    assert response_invalid.status_code == 401

@pytest.mark.asyncio
async def test_rbac_personel_cannot_access_audit_logs(personel_client: AsyncClient):
    # Personel should not access admin-only route
    response = await personel_client.get("/audit-logs/")
    assert response.status_code == 403

@pytest.mark.asyncio
async def test_rbac_admin_can_access_audit_logs(admin_client: AsyncClient):
    # Admin should access admin-only route
    response = await admin_client.get("/audit-logs/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

@pytest.mark.asyncio
async def test_rbac_personel_cannot_trigger_sim(personel_client: AsyncClient):
    response = await personel_client.post("/api/sim/tetikle?istasyon_id=1")
    assert response.status_code == 403

@pytest.mark.asyncio
async def test_rbac_admin_can_trigger_sim(admin_client: AsyncClient, test_db):
    # First create an istasyon
    from app.models import Istasyon
    istasyon = Istasyon(id=1, ad="Test İstasyon", konum="Test", tip="Depo", enlem=1.0, boylam=1.0, aktif_mi=True)
    test_db.add(istasyon)
    await test_db.commit()

    response = await admin_client.post("/api/sim/tetikle?istasyon_id=1&mod=normal")
    assert response.status_code == 200
    assert "istasyon_id" in response.json()
