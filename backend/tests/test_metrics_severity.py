import pytest
from httpx import AsyncClient
from app.main import SEVERITY_MAP
from app.metrics import anomaly_counter
from app.models import Istasyon

def test_severity_map_ascii_mapping():
    assert SEVERITY_MAP["NORMAL"] == "normal"
    assert SEVERITY_MAP["DÜŞÜK"] == "dusuk"
    assert SEVERITY_MAP["ORTA"] == "orta"
    assert SEVERITY_MAP["KRİTİK"] == "kritik"
    
    # Test fallback
    assert SEVERITY_MAP.get("BILINMEYEN", "normal") == "normal"
    
    # Verify no Turkish special lowercase characters in values (like 'ı', 'ü', 'ş')
    for key, val in SEVERITY_MAP.items():
        assert val.isascii(), f"Value {val} must be ASCII safe"

@pytest.mark.asyncio
async def test_metrics_severity_counter_increments(personel_client: AsyncClient, test_db, seed_users, mocker):
    # Setup Istasyon
    istasyon = Istasyon(id=1, ad="Merkez Depo", tip="Depo", aktif_mi=True, organization_id=seed_users["org"].id)
    test_db.add(istasyon)
    await test_db.commit()

    mocker.patch("app.main.arka_planda_analiz_et")

    # 1. Normal ölçüm (NORMAL -> "normal")
    initial_normal = anomaly_counter.labels(severity="normal")._value.get()
    res_normal = await personel_client.post("/olcumler/", json={
        "istasyon_id": 1, "ph": 7.2, "serbest_klor": 0.5, "bulaniklik": 0.4, "iletkenlik": 300, "sicaklik": 20.0
    })
    assert res_normal.status_code == 200
    assert res_normal.json()["risk_seviyesi"] == "NORMAL"
    assert anomaly_counter.labels(severity="normal")._value.get() == initial_normal + 1

    # 2. Kritik ölçüm (KRİTİK -> "kritik")
    initial_kritik = anomaly_counter.labels(severity="kritik")._value.get()
    res_kritik = await personel_client.post("/olcumler/", json={
        "istasyon_id": 1, "ph": 4.0, "serbest_klor": 0.0, "bulaniklik": 15.0, "iletkenlik": 950, "sicaklik": 35.0
    })
    assert res_kritik.status_code == 200
    assert res_kritik.json()["risk_seviyesi"] == "KRİTİK"
    assert anomaly_counter.labels(severity="kritik")._value.get() == initial_kritik + 1
