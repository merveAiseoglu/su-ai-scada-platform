import pytest
from httpx import AsyncClient
from app.models import Istasyon

@pytest.fixture
async def setup_istasyon(test_db, seed_users):
    ist = Istasyon(id=1, ad="Test İstasyon", konum="Merkez", tip="Depo", enlem=37.0, boylam=38.0, aktif_mi=True, organization_id=seed_users["org"].id)
    test_db.add(ist)
    await test_db.commit()

@pytest.mark.asyncio
async def test_create_olcum_flow(personel_client: AsyncClient, test_db, seed_users, mocker):
    # Setup Istasyon
    istasyon = Istasyon(id=1, ad="Merkez Depo", tip="Depo", aktif_mi=True, organization_id=seed_users["org"].id)
    test_db.add(istasyon)
    await test_db.commit()
    
    # Mock the background task to avoid real LLM calls
    mock_bg_task = mocker.patch("app.main.arka_planda_analiz_et")
    
    payload = {
        "istasyon_id": 1,
        "ph": 7.2,
        "serbest_klor": 0.5,
        "bulaniklik": 0.4,
        "iletkenlik": 300,
        "sicaklik": 21.0,
        "personel_notu": "Test ölçümü"
    }
    
    response = await personel_client.post("/olcumler/", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert data["istasyon_id"] == 1
    assert data["ph"] == 7.2
    assert data["risk_seviyesi"] == "NORMAL"
    assert data["analiz_durumu"] == "BEKLİYOR"
    
    # Assert background task was queued
    mock_bg_task.assert_called_once()


@pytest.mark.asyncio
async def test_list_olcumler_pagination(personel_client: AsyncClient, test_db, seed_users, mocker):
    mocker.patch("app.main.arka_planda_analiz_et")
    istasyon = Istasyon(id=2, ad="İstasyon 2", tip="Depo", aktif_mi=True, organization_id=seed_users["org"].id)
    test_db.add(istasyon)
    await test_db.commit()

    # Create 5 measurements
    for i in range(5):
        await personel_client.post("/olcumler/", json={
            "istasyon_id": 2, "ph": 7.0 + (i * 0.1), "serbest_klor": 0.5, "bulaniklik": 0.4, "iletkenlik": 300, "sicaklik": 20.0
        })

    # Page 1: limit=2, offset=0
    res_p1 = await personel_client.get("/olcumler/?limit=2&offset=0&istasyon_id=2")
    assert res_p1.status_code == 200
    data_p1 = res_p1.json()
    assert len(data_p1) == 2

    # Page 2: limit=2, offset=2
    res_p2 = await personel_client.get("/olcumler/?limit=2&offset=2&istasyon_id=2")
    assert res_p2.status_code == 200
    data_p2 = res_p2.json()
    assert len(data_p2) == 2
    assert data_p1[0]["id"] != data_p2[0]["id"]

    # Page 3: limit=2, offset=4
    res_p3 = await personel_client.get("/olcumler/?limit=2&offset=4&istasyon_id=2")
    assert res_p3.status_code == 200
    data_p3 = res_p3.json()
    assert len(data_p3) == 1

