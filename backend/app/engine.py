# app/engine.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app import models


async def hesapla_anomali_durumu(db: AsyncSession, olcum_verileri: dict):
    """
    Saha ölçüm verilerini alır, veritabanındaki dinamik anomali kuralları
    ve eşik değerleriyle karşılaştırarak en yüksek risk seviyesini ve tespitleri döndürür.
    """
    # Veritabanındaki tüm kuralları ve eşik değerlerini çek
    kurallar_result = await db.execute(select(models.AnomaliKurali))
    kurallar = kurallar_result.scalars().all()

    esikler_result = await db.execute(select(models.EsikDegeri))
    esikler = esikler_result.scalars().all()

    tespit_edilen_anomaliler = []
    en_yuksek_risk = "NORMAL"

    # Risk hiyerarşisi (sıralama önemli)
    risk_sirasi = {"NORMAL": 0, "DÜŞÜK": 1, "ORTA": 2, "KRİTİK": 3}

    # 0. Adım: ŞUSKİ Katı Güvenlik Eşikleri (Hardcoded)
    ph = olcum_verileri.get("ph")
    klor = olcum_verileri.get("serbest_klor")
    bulan = olcum_verileri.get("bulaniklik")
    ilet = olcum_verileri.get("iletkenlik")

    if ph is not None:
        if ph < 6.5:
            tespit_edilen_anomaliler.append(
                {
                    "kural": "Kritik Düşük pH",
                    "mesaj": f"Asidik Su (pH: {ph}) - Boru korozyonu ve ağır metal çözünme riski!",
                    "risk": "KRİTİK",
                }
            )
        elif ph > 8.5:
            tespit_edilen_anomaliler.append(
                {
                    "kural": "Kritik Yüksek pH",
                    "mesaj": f"Bazik Su (pH: {ph}) - Dezenfeksiyon verimsizliği!",
                    "risk": "KRİTİK",
                }
            )

    if klor is not None:
        if klor < 0.1:
            tespit_edilen_anomaliler.append(
                {"kural": "Biyolojik Risk", "mesaj": f"Klor seviyesi çok yetersiz ({klor} mg/L)!", "risk": "KRİTİK"}
            )
        elif klor < 0.2:
            tespit_edilen_anomaliler.append(
                {"kural": "Düşük Klor", "mesaj": f"Dezenfeksiyon zayıf ({klor} mg/L).", "risk": "ORTA"}
            )
        elif klor > 0.5:
            tespit_edilen_anomaliler.append(
                {"kural": "Yüksek Klor", "mesaj": f"Üst sınır aşıldı ({klor} mg/L).", "risk": "ORTA"}
            )

    if bulan is not None:
        if bulan > 5.0:
            tespit_edilen_anomaliler.append(
                {"kural": "Fiziksel Kirlilik", "mesaj": f"Kritik bulanıklık seviyesi ({bulan} NTU)!", "risk": "KRİTİK"}
            )
        elif bulan > 1.0:
            tespit_edilen_anomaliler.append(
                {"kural": "Yüksek Bulanıklık", "mesaj": f"Standart dışı bulanıklık ({bulan} NTU).", "risk": "ORTA"}
            )

    if ilet is not None:
        if ilet > 800:
            tespit_edilen_anomaliler.append(
                {"kural": "Mineral Anomalisi", "mesaj": f"Kritik seviye ({ilet} µS/cm)!", "risk": "KRİTİK"}
            )
        elif ilet > 500:
            tespit_edilen_anomaliler.append(
                {
                    "kural": "Yüksek İletkenlik",
                    "mesaj": f"Kabul edilebilir ancak yüksek ({ilet} µS/cm).",
                    "risk": "ORTA",
                }
            )
        elif ilet < 250:
            tespit_edilen_anomaliler.append(
                {
                    "kural": "Düşük İletkenlik",
                    "mesaj": f"Saf su veya ölçüm hatası ihtimali ({ilet} µS/cm).",
                    "risk": "ORTA",
                }
            )

    # 1. Adım: Basit Eşik Değer Kontrolleri (Tekil parametreler)
    for esik in esikler:
        deger = olcum_verileri.get(esik.parametre_adi)
        if deger is not None:
            if esik.min_deger is not None and deger < esik.min_deger:
                mesaj = f"{esik.parametre_adi.upper()} değeri ({deger} {esik.birim}) alt sınırın ({esik.min_deger}) altında!"
                tespit_edilen_anomaliler.append({"kural": "Alt Sınır İhlali", "mesaj": mesaj, "risk": "ORTA"})

            if esik.max_deger is not None and deger > esik.max_deger:
                mesaj = f"{esik.parametre_adi.upper()} değeri ({deger} {esik.birim}) üst sınırın ({esik.max_deger}) üzerinde!"
                tespit_edilen_anomaliler.append(
                    {
                        "kural": "Üst Sınır İhlali",
                        "mesaj": mesaj,
                        "risk": "KRİTİK" if esik.parametre_adi == "ph" else "ORTA",
                    }
                )

    # 2. Adım: Kombinasyonel Anomali Kuralları (eval() güvenli ortam mantığı)
    # Örn: "serbest_klor < 0.2 and bulaniklik > 1.0"
    context = {
        "ph": olcum_verileri.get("ph"),
        "serbest_klor": olcum_verileri.get("serbest_klor"),
        "bulaniklik": olcum_verileri.get("bulaniklik"),
        "iletkenlik": olcum_verileri.get("iletkenlik"),
        "sicaklik": olcum_verileri.get("sicaklik"),
    }

    # None değerleri eval hatası vermemesi için filtrele
    clean_context = {k: v for k, v in context.items() if v is not None}

    for kural in kurallar:
        try:
            # Kural mantığını güvenli bir şekilde çalıştır
            if eval(kural.kural_mantigi, {"__builtins__": {}}, clean_context):
                tespit_edilen_anomaliler.append(
                    {"kural": kural.kural_adi, "mesaj": kural.saha_uyarisi, "risk": kural.risk_seviyesi}
                )
        except Exception as e:
            print(f"Kural değerlendirilirken hata oluştu ({kural.kural_adi}): {e}")

    # 3. Adım: En yüksek risk seviyesini belirle
    for anomali in tespit_edilen_anomaliler:
        risk = anomali["risk"]
        if risk_sirasi.get(risk, 0) > risk_sirasi.get(en_yuksek_risk, 0):
            en_yuksek_risk = risk

    return {
        "durum": "ANOMALİ_VAR" if tespit_edilen_anomaliler else "NORMAL",
        "en_yuksek_risk_seviyesi": en_yuksek_risk,
        "detaylar": tespit_edilen_anomaliler,
    }
