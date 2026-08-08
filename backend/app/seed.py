import asyncio
from app.database import SessionLocal, engine
from app import models

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.drop_all)
        await conn.run_sync(models.Base.metadata.create_all)

async def seed_data():
    await init_db()
    
    async with SessionLocal() as db:
        try:
            # 1. Sağlık Bakanlığı Yönetmeliği Gerçek Eşik Değerleri
            esikler = [
                models.EsikDegeri(parametre_adi="ph", min_deger=6.5, max_deger=9.5, birim="pH", kaynak_url="İnsani Tüketim Amaçlı Sular Hakkında Yönetmelik"),
                models.EsikDegeri(parametre_adi="serbest_klor", min_deger=0.2, max_deger=0.5, birim="mg/L", kaynak_url="Uç nokta klor seviyesi standardı"),
                models.EsikDegeri(parametre_adi="iletkenlik", min_deger=0.0, max_deger=2500.0, birim="µS/cm", kaynak_url="20°C standart iletkenlik sınırı"),
                models.EsikDegeri(parametre_adi="bulaniklik", min_deger=0.0, max_deger=1.0, birim="NTU", kaynak_url="Tüketicilerce kabul edilebilir üst sınır"),
            ]
            db.add_all(esikler)

            # 2. Kombinasyonel Anomali Kuralları (Hardcode yerine DB'den dinamik çekilecek)
            kurallar = [
                models.AnomaliKurali(
                    kural_adi="Kritik pH Seviyesi",
                    kural_mantigi="ph < 6.5 or ph > 9.5",
                    risk_seviyesi="KRİTİK",
                    saha_uyarisi="Suyun asidik veya bazik dengesi bozulmuş. Şebekeye verilmesi uygun değildir."
                ),
                models.AnomaliKurali(
                    kural_adi="Düşük Klor + Bulanıklık",
                    kural_mantigi="serbest_klor < 0.2 and bulaniklik > 1.0",
                    risk_seviyesi="ORTA",
                    saha_uyarisi="Klor seviyesi düşük ve bulanıklık var. Mikrobiyolojik kirlilik riski yüksek, dezenfeksiyon dozu artırılmalı."
                ),
                models.AnomaliKurali(
                    kural_adi="Yüksek İletkenlik",
                    kural_mantigi="iletkenlik > 2500",
                    risk_seviyesi="DÜŞÜK",
                    saha_uyarisi="İletkenlik yasal sınırın üzerinde. Çözünmüş madde miktarında artış var."
                )
            ]
            db.add_all(kurallar)

            # 3. Örnek İstasyonlar (GIS için)
            istasyonlar = [
                models.Istasyon(ad="Merkez Su Deposu", konum="Şanlıurfa Merkez", tip="Depo", enlem=37.1674, boylam=38.7955),
                models.Istasyon(ad="Karaköprü Kuyusu", konum="Karaköprü", tip="Kuyu", enlem=37.1901, boylam=38.7885),
                models.Istasyon(ad="Haliliye Şebeke", konum="Haliliye", tip="Şebeke", enlem=37.1583, boylam=38.8078),
            ]
            db.add_all(istasyonlar)

            await db.commit()
            print("Harika! Veritabanı Sağlık Bakanlığı yönetmelik verileriyle başarıyla dolduruldu.")
        except Exception as e:
            print(f"Bir hata oluştu: {e}")
            await db.rollback()

if __name__ == "__main__":
    asyncio.run(seed_data())