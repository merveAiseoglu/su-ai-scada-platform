import asyncio

from sqlalchemy.future import select

from app.database import SessionLocal
from app.models import EsikDegeri, Organization

SEED_DATA = [
    {
        "parametre_adi": "ph",
        "min_deger": 6.5,
        "max_deger": 9.5,
        "birim": "pH",
        "kaynak_url": "TS 266 - İnsani Tüketim Amaçlı Sular Standardı",
    },
    {
        "parametre_adi": "serbest_klor",
        "min_deger": 0.2,
        "max_deger": 0.5,
        "birim": "mg/L",
        "kaynak_url": "Sağlık Bakanlığı Şebeke Suyu Klorlama Rehberi (Uç Nokta)",
    },
    {
        "parametre_adi": "iletkenlik",
        "min_deger": 0.0,
        "max_deger": 2500.0,
        "birim": "µS/cm",
        "kaynak_url": "TS 266 - İnsani Tüketim Amaçlı Sular Standardı",
    },
    {
        "parametre_adi": "bulaniklik",
        "min_deger": 0.0,
        "max_deger": 5.0,
        "birim": "NTU",
        "kaynak_url": "TS 266 - İnsani Tüketim Amaçlı Sular Standardı",
    },
    {
        "parametre_adi": "klorur",
        "min_deger": 0.0,
        "max_deger": 250.0,
        "birim": "mg/L",
        "kaynak_url": "TS 266 - Sınıf 2 Tip 2 Gösterge Özellikleri",
    },
]


async def seed_esik_degerleri():
    async with SessionLocal() as db:
        org_res = await db.execute(select(Organization).limit(1))
        default_org = org_res.scalars().first()
        if not default_org:
            default_org = Organization(name="ŞUSKİ Genel Müdürlüğü")
            db.add(default_org)
            await db.flush()

        for data in SEED_DATA:
            result = await db.execute(
                select(EsikDegeri).filter(
                    EsikDegeri.organization_id == default_org.id,
                    EsikDegeri.parametre_adi == data["parametre_adi"],
                )
            )
            existing = result.scalars().first()
            if existing:
                print(f"[ATLANDI] {data['parametre_adi']} zaten mevcut.")
            else:
                yeni_esik = EsikDegeri(**data, organization_id=default_org.id)
                db.add(yeni_esik)
                print(f"[EKLENDİ] {data['parametre_adi']} eşik değeri eklendi.")

        await db.commit()
        print("Tüm seed işlemleri tamamlandı.")


if __name__ == "__main__":
    asyncio.run(seed_esik_degerleri())
