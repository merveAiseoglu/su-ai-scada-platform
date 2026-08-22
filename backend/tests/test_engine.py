import uuid
import pytest
from app.engine import hesapla_anomali_durumu
from app.models import AnomaliKurali, EsikDegeri, Organization
from app.validators import kural_mantigi_gecerli_mi

@pytest.fixture
async def seed_engine_rules(test_db):
    org = Organization(id=uuid.uuid4(), name="Engine Test Org")
    test_db.add(org)
    await test_db.flush()

    kurallar = [
        AnomaliKurali(
            organization_id=org.id,
            kural_adi="Düşük pH Kombinasyonu",
            kural_mantigi="ph < 7.0 and serbest_klor > 1.0",
            saha_uyarisi="pH düşük ve klor yüksek, boru korozyonu riski var",
            risk_seviyesi="ORTA"
        )
    ]
    esikler = [
        EsikDegeri(
            organization_id=org.id,
            parametre_adi="ph",
            min_deger=6.5,
            max_deger=9.5,
            birim="pH"
        ),
        EsikDegeri(
            organization_id=org.id,
            parametre_adi="serbest_klor",
            min_deger=0.2,
            max_deger=2.0,
            birim="mg/L"
        )
    ]
    test_db.add_all(kurallar + esikler)
    await test_db.commit()
    return org

@pytest.mark.asyncio
async def test_hesapla_anomali_durumu_normal(test_db, seed_engine_rules):
    olcum_verileri = {
        "ph": 7.5,
        "serbest_klor": 0.5,
        "bulaniklik": 0.5,
        "iletkenlik": 300,
        "sicaklik": 20
    }
    sonuc = await hesapla_anomali_durumu(test_db, olcum_verileri, organization_id=seed_engine_rules.id)
    assert sonuc["durum"] == "NORMAL"
    assert sonuc["en_yuksek_risk_seviyesi"] == "NORMAL"
    assert len(sonuc["detaylar"]) == 0

@pytest.mark.asyncio
async def test_hesapla_anomali_durumu_kritik_ph(test_db, seed_engine_rules):
    # Boundary value checks
    olcum_verileri = {"ph": 6.4, "serbest_klor": 0.5}
    sonuc = await hesapla_anomali_durumu(test_db, olcum_verileri, organization_id=seed_engine_rules.id)
    assert sonuc["durum"] == "ANOMALİ_VAR"
    assert sonuc["en_yuksek_risk_seviyesi"] == "KRİTİK"
    assert any("Kritik Düşük pH" in d["kural"] for d in sonuc["detaylar"])

    # TS 266: pH 8.6 is normal (< 9.5)
    olcum_verileri_mid = {"ph": 8.6, "serbest_klor": 0.5, "bulaniklik": 0.5, "iletkenlik": 300}
    sonuc_mid = await hesapla_anomali_durumu(test_db, olcum_verileri_mid, organization_id=seed_engine_rules.id)
    assert sonuc_mid["en_yuksek_risk_seviyesi"] == "NORMAL"

    # pH 9.6 > 9.5 -> KRİTİK
    olcum_verileri_high = {"ph": 9.6, "serbest_klor": 0.5}
    sonuc_high = await hesapla_anomali_durumu(test_db, olcum_verileri_high, organization_id=seed_engine_rules.id)
    assert sonuc_high["en_yuksek_risk_seviyesi"] == "KRİTİK"
    assert any("Kritik Yüksek pH" in d["kural"] for d in sonuc_high["detaylar"])

@pytest.mark.asyncio
async def test_hesapla_anomali_durumu_klor_sinirlari(test_db, seed_engine_rules):
    # < 0.1 -> KRİTİK
    sonuc1 = await hesapla_anomali_durumu(test_db, {"serbest_klor": 0.05}, organization_id=seed_engine_rules.id)
    assert sonuc1["en_yuksek_risk_seviyesi"] == "KRİTİK"
    
    # < 0.2 -> ORTA
    sonuc2 = await hesapla_anomali_durumu(test_db, {"serbest_klor": 0.15}, organization_id=seed_engine_rules.id)
    assert sonuc2["en_yuksek_risk_seviyesi"] == "ORTA"
    
    # > 2.0 -> ORTA
    sonuc3 = await hesapla_anomali_durumu(test_db, {"serbest_klor": 2.5}, organization_id=seed_engine_rules.id)
    assert sonuc3["en_yuksek_risk_seviyesi"] == "ORTA"

@pytest.mark.asyncio
async def test_hesapla_anomali_durumu_bulaniklik_sinirlari(test_db):
    # TS 266: > 5.0 NTU is KRİTİK
    sonuc1 = await hesapla_anomali_durumu(test_db, {"bulaniklik": 0.5})
    assert sonuc1["en_yuksek_risk_seviyesi"] == "NORMAL"
    
    sonuc2 = await hesapla_anomali_durumu(test_db, {"bulaniklik": 5.5})
    assert sonuc2["en_yuksek_risk_seviyesi"] == "KRİTİK"

@pytest.mark.asyncio
async def test_hesapla_anomali_durumu_iletkenlik(test_db):
    sonuc1 = await hesapla_anomali_durumu(test_db, {"iletkenlik": 200})
    assert sonuc1["en_yuksek_risk_seviyesi"] == "ORTA"
    
    sonuc2 = await hesapla_anomali_durumu(test_db, {"iletkenlik": 600})
    assert sonuc2["en_yuksek_risk_seviyesi"] == "ORTA"
    
    sonuc3 = await hesapla_anomali_durumu(test_db, {"iletkenlik": 2100})
    assert sonuc3["en_yuksek_risk_seviyesi"] == "KRİTİK"

@pytest.mark.asyncio
async def test_hesapla_anomali_durumu_kombinasyon(test_db, seed_engine_rules):
    # Tests the eval() combination rule added in seed_engine_rules
    olcum_verileri = {
        "ph": 6.8,  # < 7.0
        "serbest_klor": 1.5, # > 1.0
    }
    sonuc = await hesapla_anomali_durumu(test_db, olcum_verileri, organization_id=seed_engine_rules.id)
    assert sonuc["en_yuksek_risk_seviyesi"] == "ORTA"
    assert any("Düşük pH Kombinasyonu" in d["kural"] for d in sonuc["detaylar"])

@pytest.mark.asyncio
async def test_hesapla_anomali_durumu_dusuk_risk(test_db):
    org = Organization(id=uuid.uuid4(), name="Low Risk Test Org")
    test_db.add(org)
    await test_db.flush()

    # Test DÜŞÜK risk hierarchy evaluation
    kural = AnomaliKurali(
        organization_id=org.id,
        kural_adi="Hafif Sıcaklık Sapması",
        kural_mantigi="sicaklik > 25.0",
        saha_uyarisi="Su sıcaklığı mevsim normallerinin biraz üzerinde, takip edilmeli",
        risk_seviyesi="DÜŞÜK"
    )
    test_db.add(kural)
    await test_db.commit()

    olcum_verileri = {
        "ph": 7.2,
        "serbest_klor": 0.3,
        "bulaniklik": 0.5,
        "iletkenlik": 300,
        "sicaklik": 26.5
    }
    sonuc = await hesapla_anomali_durumu(test_db, olcum_verileri, organization_id=org.id)
    assert sonuc["durum"] == "ANOMALİ_VAR"
    assert sonuc["en_yuksek_risk_seviyesi"] == "DÜŞÜK"
    assert any("Hafif Sıcaklık Sapması" in d["kural"] for d in sonuc["detaylar"])

@pytest.mark.asyncio
async def test_eval_exception_handling(test_db, seed_engine_rules):
    org = seed_engine_rules
    # Add a broken rule
    broken = AnomaliKurali(
        organization_id=org.id,
        kural_adi="Bozuk Kural",
        kural_mantigi="tanimsiz_degisken > 5",
        saha_uyarisi="Bozuk kural uyarısı",
        risk_seviyesi="KRİTİK"
    )
    test_db.add(broken)
    await test_db.commit()
    
    # It should catch the exception internally and proceed
    olcum_verileri = {"ph": 7.5}
    sonuc = await hesapla_anomali_durumu(test_db, olcum_verileri, organization_id=org.id)
    assert sonuc["durum"] == "NORMAL"


def test_kural_mantigi_gecerli_syntax():
    # Valid rule expression
    gecerli, hata = kural_mantigi_gecerli_mi("ph < 6.5")
    assert gecerli is True
    assert hata is None

    # Complex valid rule expression
    gecerli_kompleks, hata_kompleks = kural_mantigi_gecerli_mi("ph < 6.5 or (serbest_klor < 0.2 and bulaniklik > 1.0)")
    assert gecerli_kompleks is True
    assert hata_kompleks is None


def test_kural_mantigi_hatali_syntax():
    # Invalid syntax rule
    gecerli, hata = kural_mantigi_gecerli_mi("ph < and klor >")
    assert gecerli is False
    assert hata is not None
    assert "invalid syntax" in hata.lower() or "syntax" in hata.lower()

    # Empty / whitespace
    gecerli_bos, hata_bos = kural_mantigi_gecerli_mi("   ")
    assert gecerli_bos is False
    assert "boş olamaz" in hata_bos


def test_anomali_kurali_model_validation_rejects_invalid_syntax():
    # SQLAlchemy @validates("kural_mantigi") should raise ValueError on initialization
    with pytest.raises(ValueError, match="Geçersiz kural mantığı"):
        AnomaliKurali(
            organization_id=uuid.uuid4(),
            kural_adi="Sözdizimi Bozuk Kural",
            kural_mantigi="ph < and klor >",
            risk_seviyesi="KRİTİK",
            saha_uyarisi="Hata"
        )



def test_seed_validation_rejects_invalid_rule():
    # Simulating seed data with an invalid rule
    seed_candidate = [
        {"kural_adi": "Gecerli Kural", "kural_mantigi": "ph > 8.5"},
        {"kural_adi": "Hatali Kural", "kural_mantigi": "ph < and"},
    ]

    with pytest.raises(ValueError, match="Seed verisinde geçersiz kural mantığı"):
        for item in seed_candidate:
            gecerli, hata = kural_mantigi_gecerli_mi(item["kural_mantigi"])
            if not gecerli:
                raise ValueError(f"Seed verisinde geçersiz kural mantığı ({item['kural_adi']}): {hata}")


@pytest.mark.asyncio
async def test_uret_olcum_verileri_ranges(test_db):
    from app.main import _uret_olcum_verileri

    # 1. Test normal mode values stay strictly inside normal thresholds (NORMAL risk)
    for _ in range(50):
        veriler = _uret_olcum_verileri("normal")
        assert 7.0 <= veriler["ph"] <= 7.8
        assert 0.25 <= veriler["serbest_klor"] <= 0.45
        assert 0.1 <= veriler["bulaniklik"] <= 0.8
        assert 280 <= veriler["iletkenlik"] <= 380
        assert 14 <= veriler["sicaklik"] <= 22

        sonuc = await hesapla_anomali_durumu(test_db, veriler)
        assert sonuc["en_yuksek_risk_seviyesi"] == "NORMAL"
        assert len(sonuc["detaylar"]) == 0

    # 2. Test anomali mode values produce KRİTİK risk
    for _ in range(50):
        veriler = _uret_olcum_verileri("anomali")
        sonuc = await hesapla_anomali_durumu(test_db, veriler)
        assert sonuc["en_yuksek_risk_seviyesi"] == "KRİTİK"
        assert len(sonuc["detaylar"]) > 0


