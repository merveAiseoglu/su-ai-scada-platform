import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_auth_protected_rejects_missing_token(client: AsyncClient):
    response = await client.get("/istasyonlar/")
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_auth_protected_rejects_invalid_token(client: AsyncClient):
    client.headers.update({"Authorization": "Bearer invalid.token.payload"})
    response = await client.get("/istasyonlar/")
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_logout_success_and_blocklisted(personel_client: AsyncClient):
    # Perform first logout
    response1 = await personel_client.post("/logout")
    assert response1.status_code == 200
    assert response1.json()["mesaj"] == "Başarıyla çıkış yapıldı"

    # Token should now be blocklisted. A subsequent authenticated request should fail
    response2 = await personel_client.get("/istasyonlar/")
    assert response2.status_code == 401
    assert response2.json()["detail"] == "Token iptal edilmiş (Çıkış yapıldı)"

@pytest.mark.asyncio
async def test_logout_double_logout_handled_cleanly(personel_client: AsyncClient):
    # Perform first logout
    response1 = await personel_client.post("/logout")
    assert response1.status_code == 200
    
    # Perform second logout with same token, should be handled cleanly, returning 200 without 500 error
    response2 = await personel_client.post("/logout")
    assert response2.status_code == 200

@pytest.mark.asyncio
async def test_logout_malformed_token_returns_401(client: AsyncClient):
    client.headers.update({"Authorization": "Bearer invalid.token"})
    response = await client.post("/logout")
    assert response.status_code == 401
