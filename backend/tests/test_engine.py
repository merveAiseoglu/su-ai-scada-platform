import pytest
from app.engine import hesapla_anomali_durumu
from app.models import AnomaliKurali, EsikDegeri

@pytest.fixture
async def seed_engine_rules(test_db):
    kurallar = [
        AnomaliKurali(
            kural_adi="Düşük pH Kombinasyonu",
            kural_mantigi="ph < 7.0 and serbest_klor > 1.0",
            saha_uyarisi="pH düşük ve klor yüksek, boru korozyonu riski var",
            risk_seviyesi="ORTA"
        )
    ]
    esikler = [
        EsikDegeri(
            parametre_adi="ph",
            min_deger=6.5,
            max_deger=8.5,
            birim="pH"
        ),
        EsikDegeri(
            parametre_adi="serbest_klor",
            min_deger=0.2,
            max_deger=2.0,
            birim="mg/L"
        )
    ]
    test_db.add_all(kurallar + esikler)
    await test_db.commit()

@pytest.mark.asyncio
async def test_hesapla_anomali_durumu_normal(test_db, seed_engine_rules):
    olcum_verileri = {
        "ph": 7.5,
        "serbest_klor": 0.5,
        "bulaniklik": 0.5,
        "iletkenlik": 300,
        "sicaklik": 20
    }
    sonuc = await hesapla_anomali_durumu(test_db, olcum_verileri)
    assert sonuc["durum"] == "NORMAL"
    assert sonuc["en_yuksek_risk_seviyesi"] == "NORMAL"
    assert len(sonuc["detaylar"]) == 0

@pytest.mark.asyncio
async def test_hesapla_anomali_durumu_kritik_ph(test_db, seed_engine_rules):
    # Boundary value checks
    olcum_verileri = {"ph": 6.4, "serbest_klor": 0.5}
    sonuc = await hesapla_anomali_durumu(test_db, olcum_verileri)
    assert sonuc["durum"] == "ANOMALİ_VAR"
    assert sonuc["en_yuksek_risk_seviyesi"] == "KRİTİK"
    assert any("Kritik Düşük pH" in d["kural"] for d in sonuc["detaylar"])

    olcum_verileri_high = {"ph": 8.6, "serbest_klor": 0.5}
    sonuc_high = await hesapla_anomali_durumu(test_db, olcum_verileri_high)
    assert sonuc_high["en_yuksek_risk_seviyesi"] == "KRİTİK"
    assert any("Kritik Yüksek pH" in d["kural"] for d in sonuc_high["detaylar"])

@pytest.mark.asyncio
async def test_hesapla_anomali_durumu_klor_sinirlari(test_db, seed_engine_rules):
    # < 0.1 -> KRİTİK
    sonuc1 = await hesapla_anomali_durumu(test_db, {"serbest_klor": 0.05})
    assert sonuc1["en_yuksek_risk_seviyesi"] == "KRİTİK"
    
    # < 0.2 -> ORTA
    sonuc2 = await hesapla_anomali_durumu(test_db, {"serbest_klor": 0.15})
    assert sonuc2["en_yuksek_risk_seviyesi"] == "ORTA"
    
    # > 2.0 -> ORTA
    sonuc3 = await hesapla_anomali_durumu(test_db, {"serbest_klor": 2.5})
    assert sonuc3["en_yuksek_risk_seviyesi"] == "ORTA"

@pytest.mark.asyncio
async def test_hesapla_anomali_durumu_bulaniklik_sinirlari(test_db):
    sonuc1 = await hesapla_anomali_durumu(test_db, {"bulaniklik": 1.5})
    assert sonuc1["en_yuksek_risk_seviyesi"] == "ORTA"
    
    sonuc2 = await hesapla_anomali_durumu(test_db, {"bulaniklik": 5.5})
    assert sonuc2["en_yuksek_risk_seviyesi"] == "KRİTİK"

@pytest.mark.asyncio
async def test_hesapla_anomali_durumu_iletkenlik(test_db):
    sonuc1 = await hesapla_anomali_durumu(test_db, {"iletkenlik": 200})
    assert sonuc1["en_yuksek_risk_seviyesi"] == "ORTA"
    
    sonuc2 = await hesapla_anomali_durumu(test_db, {"iletkenlik": 600})
    assert sonuc2["en_yuksek_risk_seviyesi"] == "ORTA"
    
    sonuc3 = await hesapla_anomali_durumu(test_db, {"iletkenlik": 900})
    assert sonuc3["en_yuksek_risk_seviyesi"] == "KRİTİK"

@pytest.mark.asyncio
async def test_hesapla_anomali_durumu_kombinasyon(test_db, seed_engine_rules):
    # Tests the eval() combination rule added in seed_engine_rules
    olcum_verileri = {
        "ph": 6.8,  # < 7.0
        "serbest_klor": 1.5, # > 1.0
    }
    sonuc = await hesapla_anomali_durumu(test_db, olcum_verileri)
    assert sonuc["en_yuksek_risk_seviyesi"] == "ORTA"
    assert any("Düşük pH Kombinasyonu" in d["kural"] for d in sonuc["detaylar"])

@pytest.mark.asyncio
async def test_eval_exception_handling(test_db, seed_engine_rules):
    # Add a broken rule
    broken = AnomaliKurali(
        kural_adi="Bozuk Kural",
        kural_mantigi="tanimsiz_degisken > 5",
        saha_uyarisi="Bozuk kural uyarısı",
        risk_seviyesi="KRİTİK"
    )
    test_db.add(broken)
    await test_db.commit()
    
    # It should catch the exception internally and proceed
    olcum_verileri = {"ph": 7.5}
    sonuc = await hesapla_anomali_durumu(test_db, olcum_verileri)
    assert sonuc["durum"] == "NORMAL"
