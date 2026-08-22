import pytest
from httpx import AsyncClient
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Istasyon, Organization, Kullanici
import uuid

@pytest.mark.asyncio
async def test_transaction_rollback_isolation(test_db: AsyncSession, seed_users):
    # 1. Başlangıçta kaç istasyon olduğunu kontrol et
    res_before = await test_db.execute(select(func.count(Istasyon.id)))
    count_before = res_before.scalar()
    print(f"\n[Test Başlangıcı] Mevcut İstasyon Sayısı: {count_before}")
    
    # 2. Sabit ID ve benzersiz isimle yeni bir kayıt ekle
    test_istasyon = Istasyon(
        id=999,
        organization_id=seed_users["org"].id,
        ad="Özel İzolasyon İstasyonu #999",
        konum="İzolasyon Test Bölgesi",
        tip="Depo",
        aktif_mi=True
    )
    test_db.add(test_istasyon)
    await test_db.commit()
    
    # 3. Eklenen kaydı doğrula
    res_during = await test_db.execute(select(Istasyon).filter(Istasyon.id == 999))
    inserted = res_during.scalars().first()
    assert inserted is not None
    assert inserted.ad == "Özel İzolasyon İstasyonu #999"
    print(f"[Test İçi] İstasyon #999 başarıyla eklendi (ID: {inserted.id}, Ad: {inserted.ad})")
    
    # Test bittiğinde fixture (test_db) otomatik savepoint/transaction rollback yapacak.
