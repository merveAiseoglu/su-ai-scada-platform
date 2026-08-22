import pytest
import uuid
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Organization, Kullanici, Istasyon, SuOlcumu
from app.auth import get_password_hash, create_access_token

@pytest.fixture
async def multi_tenant_setup(test_db: AsyncSession, seed_users):
    org_a = seed_users["org"]
    admin_a = seed_users["admin"]
    
    # Create Org B
    org_b = Organization(id=uuid.uuid4(), name="Org B")
    test_db.add(org_b)
    await test_db.commit()
    
    # Create Admin for Org B
    admin_b = Kullanici(
        email="admin_b@test.com",
        sifre_hash=get_password_hash("admin123"),
        rol="yonetici",
        aktif_mi=True,
        organization_id=org_b.id
    )
    test_db.add(admin_b)
    await test_db.commit()
    
    # Create Stations
    ist_a = Istasyon(id=101, ad="Station A", tip="Depo", aktif_mi=True, organization_id=org_a.id)
    ist_b = Istasyon(id=102, ad="Station B", tip="Depo", aktif_mi=True, organization_id=org_b.id)
    test_db.add_all([ist_a, ist_b])
    await test_db.commit()

    # Create Measurements
    olcum_a = SuOlcumu(istasyon_id=101, ph=7.1)
    olcum_b = SuOlcumu(istasyon_id=102, ph=7.5)
    test_db.add_all([olcum_a, olcum_b])
    await test_db.commit()

    token_b = create_access_token(data={"sub": admin_b.email, "rol": "yonetici"})
    return {"org_a": org_a, "org_b": org_b, "token_b": token_b}

@pytest.mark.asyncio
async def test_multi_tenancy_isolation(admin_client: AsyncClient, client: AsyncClient, multi_tenant_setup):
    token_b = multi_tenant_setup["token_b"]
    headers_b = {"Authorization": f"Bearer {token_b}"}
    
    # Admin A requests stations, should only see Station A (id=101)
    resp_a = await admin_client.get("/istasyonlar/")
    assert resp_a.status_code == 200
    data_a = resp_a.json()
    assert len(data_a) == 1
    assert data_a[0]["ad"] == "Station A"
    
    # Admin B requests stations, should only see Station B (id=102)
    resp_b = await client.get("/istasyonlar/", headers=headers_b)
    assert resp_b.status_code == 200
    data_b = resp_b.json()
    assert len(data_b) == 1
    assert data_b[0]["ad"] == "Station B"

    # Admin A requests measurements, should only see olcum_a (ph 7.1)
    resp_meas_a = await admin_client.get("/olcumler/")
    assert resp_meas_a.status_code == 200
    meas_a = resp_meas_a.json()
    assert len(meas_a) == 1
    assert meas_a[0]["ph"] == 7.1
    
    # Admin B requests measurements, should only see olcum_b (ph 7.5)
    resp_meas_b = await client.get("/olcumler/", headers=headers_b)
    assert resp_meas_b.status_code == 200
    meas_b = resp_meas_b.json()
    assert len(meas_b) == 1
    assert meas_b[0]["ph"] == 7.5


@pytest.mark.asyncio
async def test_multi_tenancy_threshold_and_rule_isolation(
    admin_client: AsyncClient, client: AsyncClient, multi_tenant_setup, test_db: AsyncSession
):
    from app.engine import hesapla_anomali_durumu

    token_b = multi_tenant_setup["token_b"]
    headers_b = {"Authorization": f"Bearer {token_b}"}
    org_a = multi_tenant_setup["org_a"]
    org_b = multi_tenant_setup["org_b"]

    # 1. Admin A creates custom threshold and rule
    resp_esik_a = await admin_client.post(
        "/api/admin/esikler",
        json={"parametre_adi": "bulaniklik", "min_deger": 0.0, "max_deger": 1.0, "birim": "NTU"}
    )
    assert resp_esik_a.status_code == 200
    esik_a_id = resp_esik_a.json()["id"]

    resp_kural_a = await admin_client.post(
        "/api/admin/kurallar",
        json={"kural_adi": "Org A Özel pH Kuralı", "kural_mantigi": "ph > 8.0", "risk_seviyesi": "KRİTİK", "saha_uyarisi": "Org A Uyarısı"}
    )
    assert resp_kural_a.status_code == 200
    kural_a_id = resp_kural_a.json()["id"]

    # 2. Admin B creates different threshold for same parameter name and different rule
    resp_esik_b = await client.post(
        "/api/admin/esikler",
        headers=headers_b,
        json={"parametre_adi": "bulaniklik", "min_deger": 0.0, "max_deger": 4.0, "birim": "NTU"}
    )
    assert resp_esik_b.status_code == 200
    esik_b_id = resp_esik_b.json()["id"]

    resp_kural_b = await client.post(
        "/api/admin/kurallar",
        headers=headers_b,
        json={"kural_adi": "Org B Özel pH Kuralı", "kural_mantigi": "ph > 8.8", "risk_seviyesi": "ORTA", "saha_uyarisi": "Org B Uyarısı"}
    )
    assert resp_kural_b.status_code == 200
    kural_b_id = resp_kural_b.json()["id"]

    # 3. Verify listing isolation
    list_a = await admin_client.get("/api/admin/esikler")
    assert len(list_a.json()) == 1
    assert list_a.json()[0]["max_deger"] == 1.0

    list_b = await client.get("/api/admin/esikler", headers=headers_b)
    assert len(list_b.json()) == 1
    assert list_b.json()[0]["max_deger"] == 4.0

    # 4. Engine isolation: ph=8.2 triggers KRİTİK for Org A (ph > 8.0), but NORMAL for Org B (ph > 8.8)
    olcum_test = {"ph": 8.2}
    sonuc_a = await hesapla_anomali_durumu(test_db, olcum_test, organization_id=org_a.id)
    assert sonuc_a["en_yuksek_risk_seviyesi"] == "KRİTİK"

    sonuc_b = await hesapla_anomali_durumu(test_db, olcum_test, organization_id=org_b.id)
    assert sonuc_b["en_yuksek_risk_seviyesi"] == "NORMAL"

    # 5. Cross-tenant update prevention: Admin B cannot update Org A's threshold or rule
    cross_up_esik = await client.put(f"/api/admin/esikler/{esik_a_id}", headers=headers_b, json={"max_deger": 99.0})
    assert cross_up_esik.status_code == 404

    cross_up_kural = await client.put(f"/api/admin/kurallar/{kural_a_id}", headers=headers_b, json={"kural_adi": "Hacked"})
    assert cross_up_kural.status_code == 404


@pytest.mark.asyncio
async def test_admin_endpoints_rbac_personel_forbidden(personel_client: AsyncClient):
    # RBAC: Saha personeli cannot access admin endpoints (403 Forbidden)
    resp_get_esik = await personel_client.get("/api/admin/esikler")
    assert resp_get_esik.status_code == 403

    resp_post_esik = await personel_client.post("/api/admin/esikler", json={"parametre_adi": "ph", "birim": "pH"})
    assert resp_post_esik.status_code == 403

    resp_get_kural = await personel_client.get("/api/admin/kurallar")
    assert resp_get_kural.status_code == 403

    resp_post_kural = await personel_client.post("/api/admin/kurallar", json={"kural_adi": "Kural", "kural_mantigi": "ph < 6", "risk_seviyesi": "ORTA", "saha_uyarisi": "U"})
    assert resp_post_kural.status_code == 403


@pytest.mark.asyncio
async def test_admin_endpoints_syntax_validation(admin_client: AsyncClient):
    # Syntax validation: Invalid Python syntax is rejected with 400 Bad Request
    resp_invalid_syntax = await admin_client.post(
        "/api/admin/kurallar",
        json={"kural_adi": "Bozuk Syntax", "kural_mantigi": "ph < and klor >", "risk_seviyesi": "KRİTİK", "saha_uyarisi": "Hata"}
    )
    assert resp_invalid_syntax.status_code == 400
    assert "Geçersiz kural mantığı" in resp_invalid_syntax.json()["detail"]

