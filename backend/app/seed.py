import asyncio

from sqlalchemy.future import select

from app import models
from app.database import SessionLocal, engine
from app.validators import kural_mantigi_gecerli_mi


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.drop_all)
        await conn.run_sync(models.Base.metadata.create_all)


async def seed_data():
    await init_db()

    async with SessionLocal() as db:
        try:
            # 0. Varsayılan Organizasyon
            org_res = await db.execute(select(models.Organization).limit(1))
            default_org = org_res.scalars().first()
            if not default_org:
                default_org = models.Organization(name="ŞUSKİ Genel Müdürlüğü")
                db.add(default_org)
                await db.flush()

            # 1. Sağlık Bakanlığı Yönetmeliği Gerçek Eşik Değerleri
            esikler = [
                models.EsikDegeri(
                    organization_id=default_org.id,
                    parametre_adi="ph",
                    min_deger=6.5,
                    max_deger=9.5,
                    birim="pH",
                    kaynak_url="İnsani Tüketim Amaçlı Sular Hakkında Yönetmelik",
                ),
                models.EsikDegeri(
                    organization_id=default_org.id,
                    parametre_adi="serbest_klor",
                    min_deger=0.2,
                    max_deger=0.5,
                    birim="mg/L",
                    kaynak_url="Uç nokta klor seviyesi standardı",
                ),
                models.EsikDegeri(
                    organization_id=default_org.id,
                    parametre_adi="iletkenlik",
                    min_deger=0.0,
                    max_deger=2500.0,
                    birim="µS/cm",
                    kaynak_url="20°C standart iletkenlik sınırı",
                ),
                models.EsikDegeri(
                    organization_id=default_org.id,
                    parametre_adi="bulaniklik",
                    min_deger=0.0,
                    max_deger=1.0,
                    birim="NTU",
                    kaynak_url="Tüketicilerce kabul edilebilir üst sınır",
                ),
            ]
            db.add_all(esikler)

            # 2. Kombinasyonel Anomali Kuralları (Hardcode yerine DB'den dinamik çekilecek)
            kurallar = [
                models.AnomaliKurali(
                    organization_id=default_org.id,
                    kural_adi="Kritik pH Seviyesi",
                    kural_mantigi="ph < 6.5 or ph > 9.5",
                    risk_seviyesi="KRİTİK",
                    saha_uyarisi="Suyun asidik veya bazik dengesi bozulmuş. Şebekeye verilmesi uygun değildir.",
                ),
                # Not: Buradaki 1.0 NTU değeri kritik bulanıklık eşiğinden (5.0 NTU) farklıdır;
                # burada düşük klorla birlikte kombinasyonel erken uyarı amacıyla bilinçli olarak daha düşük tutulmuştur.
                models.AnomaliKurali(
                    organization_id=default_org.id,
                    kural_adi="Düşük Klor + Bulanıklık",
                    kural_mantigi="serbest_klor < 0.2 and bulaniklik > 1.0",
                    risk_seviyesi="ORTA",
                    saha_uyarisi="Klor seviyesi düşük ve bulanıklık var. Mikrobiyolojik kirlilik riski yüksek, dezenfeksiyon dozu artırılmalı.",
                ),
                # Not: Önceki 'iletkenlik > 2500' kuralı, engine.py içerisindeki hardcoded TS 266 KRİTİK (>2000)
                # ve ORTA (>400) kurallarının gölgesinde kaldığı ve hiçbir zaman nihai risk sonucunu belirleyemediği için
                # DÜŞÜK seviye kuralı su kalitesi ve klor stabilitesi açısından kritik olan 'sıcaklık' parametresine taşındı.
                models.AnomaliKurali(
                    organization_id=default_org.id,
                    kural_adi="Yüksek Sıcaklık",
                    kural_mantigi="sicaklik > 25.0",
                    risk_seviyesi="DÜŞÜK",
                    saha_uyarisi="Su sıcaklığı mevsim normallerinin üzerinde (25°C üzeri). Yüksek sıcaklık klor uçuculuğunu artırabilir ve mikrobiyolojik üremeyi hızlandırabilir, klor seviyesi yakından takip edilmelidir.",
                ),
            ]
            for k in kurallar:
                gecerli, hata = kural_mantigi_gecerli_mi(k.kural_mantigi)
                if not gecerli:
                    raise ValueError(f"Seed verisinde geçersiz kural mantığı ({k.kural_adi}): {hata}")
            db.add_all(kurallar)

            # 3. Örnek İstasyonlar (GIS için)
            istasyonlar = [
                models.Istasyon(
                    organization_id=default_org.id,
                    ad="Merkez Su Deposu", konum="Şanlıurfa Merkez", tip="Depo", enlem=37.1674, boylam=38.7955
                ),
                models.Istasyon(
                    organization_id=default_org.id,
                    ad="Karaköprü Kuyusu", konum="Karaköprü", tip="Kuyu", enlem=37.1901, boylam=38.7885
                ),
                models.Istasyon(
                    organization_id=default_org.id,
                    ad="Haliliye Şebeke", konum="Haliliye", tip="Şebeke", enlem=37.1583, boylam=38.8078
                ),
            ]
            db.add_all(istasyonlar)

            await db.commit()
            print("Harika! Veritabanı Sağlık Bakanlığı yönetmelik verileriyle başarıyla dolduruldu.")
        except Exception as e:
            print(f"Bir hata oluştu: {e}")
            await db.rollback()


if __name__ == "__main__":
    asyncio.run(seed_data())
