import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_pdf_report_admin_success(admin_client: AsyncClient, test_db, seed_users):
    from app.models import Istasyon, SuOlcumu
    import datetime
    
    istasyon = Istasyon(id=999, ad="Report Station", tip="Depo", aktif_mi=True, organization_id=seed_users["org"].id)
    olcum = SuOlcumu(istasyon_id=999, ph=7.2, olcum_tarihi=datetime.datetime.now())
    test_db.add(istasyon)
    test_db.add(olcum)
    await test_db.commit()

    response = await admin_client.get("/admin/reports/monthly")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert len(response.content) > 100  # valid PDF content

@pytest.mark.asyncio
async def test_pdf_report_personel_forbidden(personel_client: AsyncClient):
    response = await personel_client.get("/admin/reports/monthly")
    assert response.status_code == 403
