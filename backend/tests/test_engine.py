import pytest
from unittest.mock import AsyncMock, MagicMock
from app.engine import hesapla_anomali_durumu
from app import models

@pytest.mark.asyncio
async def test_hesapla_anomali_durumu_normal():
    # 1. Mock the DB Session
    mock_db = AsyncMock()
    
    # 2. Mock AnomaliKurali and EsikDegeri DB returns
    mock_kurallar_result = MagicMock()
    mock_kurallar_result.scalars().all.return_value = []
    
    mock_esikler_result = MagicMock()
    esik_ph = models.EsikDegeri(parametre_adi="ph", min_deger=6.5, max_deger=9.5, birim="pH")
    esik_klor = models.EsikDegeri(parametre_adi="serbest_klor", min_deger=0.2, max_deger=0.5, birim="mg/L")
    mock_esikler_result.scalars().all.return_value = [esik_ph, esik_klor]
    
    mock_db.execute.side_effect = [mock_kurallar_result, mock_esikler_result]
    
    # 3. Create normal measurement data
    olcum_verileri = {
        "ph": 7.5,
        "serbest_klor": 0.3,
        "bulaniklik": 0.2,
        "iletkenlik": 800.0,
        "sicaklik": 22.0
    }
    
    # 4. Call the engine
    sonuc = await hesapla_anomali_durumu(mock_db, olcum_verileri)
    
    # 5. Assertions for normal state
    assert sonuc["durum"] == "NORMAL"
    assert sonuc["en_yuksek_risk_seviyesi"] == "NORMAL"
    assert len(sonuc["detaylar"]) == 0

@pytest.mark.asyncio
async def test_hesapla_anomali_durumu_riskli():
    mock_db = AsyncMock()
    
    mock_kurallar_result = MagicMock()
    mock_kurallar_result.scalars().all.return_value = []
    
    mock_esikler_result = MagicMock()
    esik_ph = models.EsikDegeri(parametre_adi="ph", min_deger=6.5, max_deger=9.5, birim="pH")
    esik_klor = models.EsikDegeri(parametre_adi="serbest_klor", min_deger=0.2, max_deger=0.5, birim="mg/L")
    mock_esikler_result.scalars().all.return_value = [esik_ph, esik_klor]
    
    mock_db.execute.side_effect = [mock_kurallar_result, mock_esikler_result]
    
    # Anomalous measurement data: pH is too high (10.0), serbest_klor is too low (0.1)
    olcum_verileri = {
        "ph": 10.0,
        "serbest_klor": 0.1,
    }
    
    sonuc = await hesapla_anomali_durumu(mock_db, olcum_verileri)
    
    assert sonuc["durum"] == "ANOMALİ_VAR"
    assert sonuc["en_yuksek_risk_seviyesi"] == "KRİTİK" # pH upper bound violation is mapped to KRITIK in engine
    assert len(sonuc["detaylar"]) == 2
    
    # Asserting details
    kurallar = [detay["kural"] for detay in sonuc["detaylar"]]
    assert "Üst Sınır İhlali" in kurallar
    assert "Alt Sınır İhlali" in kurallar
