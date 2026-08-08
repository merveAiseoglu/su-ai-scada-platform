import pytest
from httpx import AsyncClient
from app.models import Istasyon

@pytest.fixture
async def setup_istasyon(test_db):
    ist = Istasyon(id=1, ad="Test İstasyon", konum="Merkez", tip="Depo", enlem=37.0, boylam=38.0, aktif_mi=True)
    test_db.add(ist)
    await test_db.commit()

@pytest.mark.asyncio
async def test_create_olcum_flow(personel_client: AsyncClient, setup_istasyon, mocker):
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
