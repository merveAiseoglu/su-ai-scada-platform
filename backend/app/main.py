# app/main.py  —  Su-AI API v4.0  (Asenkron LLM + BackgroundTasks)
import datetime as _dt
import random
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import List

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app import models, schemas
from app.auth import ACCESS_TOKEN_EXPIRE_MINUTES, create_access_token, log_audit, require_role, verify_password
from app.database import DEV_DROP_RECREATE, SessionLocal, engine, get_db
from app.engine import hesapla_anomali_durumu
from app.llm_service import arka_planda_analiz_et


# ---------------------------------------------------------------------------
# Veritabanı başlangıç — Geliştirme ortamında tabloları sıfırdan oluştur
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    if DEV_DROP_RECREATE:
        async with engine.begin() as conn:
            # FK bağımlılığı nedeniyle önce analiz_metrikleri, sonra su_olcumleri drop edilmeli
            await conn.run_sync(models.AnalizMetrikleri.__table__.drop, checkfirst=True)
            await conn.run_sync(models.SuOlcumu.__table__.drop, checkfirst=True)
            await conn.run_sync(models.AuditLog.__table__.drop, checkfirst=True)
            await conn.run_sync(models.Kullanici.__table__.drop, checkfirst=True)
            print("[DEV] Eski tablolar silindi - yeniden olusturuluyor.")

    async with engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)

        # Admin kullanicisi olustur (Eger yoksa)
        result = await conn.execute(select(models.Kullanici).filter(models.Kullanici.email == "admin@suski.gov.tr"))
        admin = result.fetchone()
        if not admin:
            from app.auth import get_password_hash

            await conn.execute(
                models.Kullanici.__table__.insert().values(
                    email="admin@suski.gov.tr", sifre_hash=get_password_hash("admin123"), rol="yonetici", aktif_mi=True
                )
            )
            print("[OK] Varsayilan yonetici (admin@suski.gov.tr) eklendi.")

        # Personel kullanicisi olustur (Eger yoksa)
        result_pers = await conn.execute(
            select(models.Kullanici).filter(models.Kullanici.email == "personel1@suski.gov.tr")
        )
        personel = result_pers.fetchone()
        if not personel:
            from app.auth import get_password_hash

            await conn.execute(
                models.Kullanici.__table__.insert().values(
                    email="personel1@suski.gov.tr",
                    sifre_hash=get_password_hash("pers123"),
                    rol="saha_personeli",
                    aktif_mi=True,
                )
            )
            print("[OK] Varsayilan personel (personel1@suski.gov.tr) eklendi.")

        # Ornek Istasyonlar
        ist_result = await conn.execute(select(models.Istasyon).filter(models.Istasyon.ad == "Merkez Su Deposu"))
        if not ist_result.fetchone():
            await conn.execute(
                models.Istasyon.__table__.insert().values(
                    [
                        {
                            "ad": "Merkez Su Deposu",
                            "konum": "Şanlıurfa Merkez",
                            "tip": "Depo",
                            "enlem": 37.1674,
                            "boylam": 38.7955,
                            "aktif_mi": True,
                        },
                        {
                            "ad": "Karaköprü Kuyusu",
                            "konum": "Karaköprü",
                            "tip": "Kuyu",
                            "enlem": 37.1901,
                            "boylam": 38.7885,
                            "aktif_mi": True,
                        },
                        {
                            "ad": "Haliliye Şebeke",
                            "konum": "Haliliye",
                            "tip": "Şebeke",
                            "enlem": 37.1583,
                            "boylam": 38.8078,
                            "aktif_mi": True,
                        },
                    ]
                )
            )
            print("[OK] Örnek istasyonlar eklendi.")

    print("[OK] Veritabani tablolari hazir.")

    # RAG Modelini Preload yap (Asyncio thread'de çalıştırarak FastAPI'yi kilitlemeyi önle)
    import asyncio

    from app.rag_service import preload_rag_model

    await asyncio.to_thread(preload_rag_model)

    yield


# ---------------------------------------------------------------------------
# FastAPI uygulaması
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Su-AI API",
    description="Şanlıurfa Su İşleri — Su Kalitesi İzleme ve Karar Destek Sistemi",
    version="4.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Yardımcı fonksiyonlar
# ---------------------------------------------------------------------------


def _olcum_to_analiz_girdisi(olcum: models.SuOlcumu) -> dict:
    """SuOlcumu DB nesnesini kural motoru için dict'e çevirir."""
    return {
        "ph": olcum.ph,
        "serbest_klor": olcum.serbest_klor,
        "bulaniklik": olcum.bulaniklik,
        "iletkenlik": olcum.iletkenlik,
        "sicaklik": olcum.sicaklik,
    }


async def _olcum_to_response(
    olcum: models.SuOlcumu,
    analiz_sonucu: dict | None = None,
    db: AsyncSession | None = None,
) -> schemas.SuOlcumuResponse:
    """ORM nesnesini response şemasına dönüştürür.
    - analiz_sonucu: isteğe bağlı kural motoru detayları
    - db: verilmişse AnalizMetrikleri tablosundan metrik çeker
    """
    data = schemas.SuOlcumuResponse.model_validate(olcum)
    data.analiz_sonucu = analiz_sonucu

    # Metrik bilgisini DB'den çek (analiz tamamlandıysa mevcuttur)
    if db is not None:
        result = await db.execute(select(models.AnalizMetrikleri).filter(models.AnalizMetrikleri.olcum_id == olcum.id))
        metrik = result.scalars().first()
        if metrik:
            data.metrikler = schemas.AnalizMetrikleriResponse.model_validate(metrik)

    return data


# ---------------------------------------------------------------------------
# Genel
# ---------------------------------------------------------------------------


@app.get("/", tags=["Genel"])
async def read_root():
    return {"mesaj": "Su-AI API Sistemine Hoş Geldiniz", "versiyon": "4.0.0"}


# ---------------------------------------------------------------------------
# Kimlik Doğrulama Endpoint'i
# ---------------------------------------------------------------------------


@app.post("/token", response_model=schemas.Token, tags=["Kimlik Doğrulama"])
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.Kullanici).filter(models.Kullanici.email == form_data.username))
    user = result.scalars().first()

    if not user or not verify_password(form_data.password, user.sifre_hash):
        raise HTTPException(status_code=401, detail="Hatalı e-posta veya şifre", headers={"WWW-Authenticate": "Bearer"})

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": user.email, "rol": user.rol}, expires_delta=access_token_expires)

    # Audit log
    await log_audit(db, kullanici_id=user.id, islem_tipi="LOGIN", detay="Kullanıcı sisteme giriş yaptı.")

    return {"access_token": access_token, "token_type": "bearer"}


# ---------------------------------------------------------------------------
# İstasyon Endpoint'leri
# ---------------------------------------------------------------------------


@app.post("/istasyonlar/", response_model=schemas.IstasyonResponse, tags=["İstasyonlar"])
async def create_istasyon(
    istasyon: schemas.IstasyonCreate,
    db: AsyncSession = Depends(get_db),
    current_user: models.Kullanici = Depends(require_role(["yonetici"])),
):
    db_istasyon = models.Istasyon(**istasyon.model_dump())
    db.add(db_istasyon)
    await db.commit()
    await db.refresh(db_istasyon)

    # Audit log
    await log_audit(
        db, kullanici_id=current_user.id, islem_tipi="ISTASYON_EKLENDI", detay=f"Yeni istasyon eklendi: {istasyon.ad}"
    )

    return db_istasyon


@app.get("/istasyonlar/", response_model=List[schemas.IstasyonResponse], tags=["İstasyonlar"])
async def read_istasyonlar(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: models.Kullanici = Depends(require_role(["saha_personeli", "yonetici"])),
):
    result = await db.execute(select(models.Istasyon).offset(skip).limit(limit))
    return result.scalars().all()


@app.get("/istasyonlar/{istasyon_id}", response_model=schemas.IstasyonResponse, tags=["İstasyonlar"])
async def read_istasyon(
    istasyon_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.Kullanici = Depends(require_role(["saha_personeli", "yonetici"])),
):
    result = await db.execute(select(models.Istasyon).filter(models.Istasyon.id == istasyon_id))
    istasyon = result.scalars().first()
    if not istasyon:
        raise HTTPException(status_code=404, detail="İstasyon bulunamadı")
    return istasyon


# ---------------------------------------------------------------------------
# GIS / Harita Endpoint'leri
# ---------------------------------------------------------------------------


@app.get("/api/gis/istasyonlar", response_model=List[schemas.GisIstasyonResponse], tags=["GIS"])
async def get_gis_istasyonlar(
    db: AsyncSession = Depends(get_db),
    current_user: models.Kullanici = Depends(require_role(["saha_personeli", "yonetici"])),
):
    result = await db.execute(select(models.Istasyon).filter(models.Istasyon.aktif_mi.is_(True)))
    istasyonlar = result.scalars().all()

    gis_data = []
    for ist in istasyonlar:
        olcum_result = await db.execute(
            select(models.SuOlcumu)
            .filter(models.SuOlcumu.istasyon_id == ist.id)
            .order_by(models.SuOlcumu.olcum_tarihi.desc())
            .limit(1)
        )
        son_olcum = olcum_result.scalars().first()

        ist_dict = ist.__dict__.copy()
        if son_olcum:
            ist_dict["son_olcum_tarihi"] = son_olcum.olcum_tarihi
            ist_dict["son_risk_seviyesi"] = son_olcum.risk_seviyesi
            ist_dict["son_personel_notu"] = son_olcum.personel_notu
            # Sensör değerleri — harita callout için
            ist_dict["son_ph"] = son_olcum.ph
            ist_dict["son_serbest_klor"] = son_olcum.serbest_klor
            ist_dict["son_bulaniklik"] = son_olcum.bulaniklik
            ist_dict["son_iletkenlik"] = son_olcum.iletkenlik
            ist_dict["son_sicaklik"] = son_olcum.sicaklik
            ist_dict["son_analiz_durumu"] = son_olcum.analiz_durumu
            ist_dict["son_olcum_id"] = son_olcum.id  # ResultScreen navigasyonu

        gis_data.append(ist_dict)

    return gis_data


# ---------------------------------------------------------------------------
# Ölçüm Endpoint'leri
# ---------------------------------------------------------------------------


@app.get("/olcumler/", response_model=List[schemas.SuOlcumuResponse], tags=["Ölçümler"])
async def list_olcumler(
    istasyon_id: int | None = None,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: models.Kullanici = Depends(require_role(["saha_personeli", "yonetici"])),
):
    """
    Son ölçümleri listeler. Opsiyonel istasyon_id filtresi ve limit parametresi desteklenir.
    SimulatorScreen ve dashboard için kullanılır.
    """
    q = select(models.SuOlcumu).order_by(models.SuOlcumu.olcum_tarihi.desc()).limit(limit)
    if istasyon_id is not None:
        q = q.filter(models.SuOlcumu.istasyon_id == istasyon_id)
    result = await db.execute(q)
    return result.scalars().all()


@app.post("/olcumler/", response_model=schemas.SuOlcumuResponse, tags=["Ölçümler"])
@app.post(
    "/su-olcumu",
    response_model=schemas.SuOlcumuResponse,
    tags=["Ölçümler"],
    description="Aşama 2 için /olcumler/ uç noktasının alias'ı",
)
async def create_olcum(
    olcum: schemas.SuOlcumuCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: models.Kullanici = Depends(require_role(["saha_personeli", "yonetici"])),
):
    """
    Yeni ölçüm kaydeder ve LLM analizini arka plana atar.
    Sadece yetkili kullanıcılar erişebilir.
    """
    # 1. İstasyon kontrolü
    result = await db.execute(select(models.Istasyon).filter(models.Istasyon.id == olcum.istasyon_id))
    istasyon = result.scalars().first()
    if not istasyon:
        raise HTTPException(status_code=404, detail=f"İstasyon (id={olcum.istasyon_id}) bulunamadı")

    # 2. Ölçümü kaydet — analiz_durumu varsayılan "BEKLİYOR"
    db_olcum = models.SuOlcumu(**olcum.model_dump())
    db.add(db_olcum)
    await db.commit()
    await db.refresh(db_olcum)

    # Audit log'a kaydet
    await log_audit(
        db,
        kullanici_id=current_user.id,
        islem_tipi="OLCUM_EKLENDI",
        detay=f"İstasyon {olcum.istasyon_id} için yeni ölçüm girildi.",
    )

    # 3. Kural motorunu çalıştır (senkron, ~ms) — risk_seviyesi'ni hemen yaz
    analiz_girdisi = _olcum_to_analiz_girdisi(db_olcum)
    kural_motoru_sonucu = await hesapla_anomali_durumu(db, analiz_girdisi)

    db_olcum.risk_seviyesi = kural_motoru_sonucu.get("en_yuksek_risk_seviyesi", "NORMAL")
    await db.commit()
    await db.refresh(db_olcum)

    # 4. LLM görevini arka plana at — SessionLocal factory geçilir (thread-safe)
    background_tasks.add_task(arka_planda_analiz_et, db_olcum.id, SessionLocal)

    # 5. analiz_durumu="BEKLİYOR" ile anında dön (kural motoru detaylarını da ekle)
    return await _olcum_to_response(db_olcum, analiz_sonucu=kural_motoru_sonucu)


@app.get("/olcumler/{olcum_id}", response_model=schemas.SuOlcumuResponse, tags=["Ölçümler"])
async def read_olcum(
    olcum_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.Kullanici = Depends(require_role(["saha_personeli", "yonetici"])),
):
    """
    Belirli bir ölçümün güncel durumunu döner.
    """
    result = await db.execute(select(models.SuOlcumu).filter(models.SuOlcumu.id == olcum_id))
    olcum = result.scalars().first()
    if not olcum:
        raise HTTPException(status_code=404, detail="Ölçüm bulunamadı")
    return await _olcum_to_response(olcum, db=db)


# ---------------------------------------------------------------------------
# Audit Log Endpoint (Denetim İzi)
# ---------------------------------------------------------------------------


@app.get("/audit-logs/", response_model=List[schemas.AuditLogResponse], tags=["Denetim İzi"])
async def get_audit_logs(
    limit: int = 100,
    islem_tipi: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: models.Kullanici = Depends(require_role(["yonetici"])),
):
    """
    Son denetim izi kayıtlarını döner.
    Kimin ne zaman ne yaptığını izlemek için kullanılır.
    Sadece yönetici rolü erişebilir.
    """
    q = select(models.AuditLog).order_by(models.AuditLog.timestamp.desc()).limit(limit)
    if islem_tipi:
        q = q.filter(models.AuditLog.islem_tipi == islem_tipi)
    result = await db.execute(q)
    return result.scalars().all()


# ---------------------------------------------------------------------------
# Faz 4 — IoT Simülasyon Endpoint'leri
# ---------------------------------------------------------------------------

# Basit in-memory simülatör durum kaydı
_sim_durum = {"toplam": 0, "son_tetikle": None, "son_istasyon_id": None}


def _uret_olcum_verileri(mod: str = "karisik") -> dict:
    """Seçilen moda göre rastgele veya anomali içeren sensör değerleri üretir."""
    if mod == "normal":
        return {
            "ph": round(random.uniform(7.0, 7.8), 2),
            "serbest_klor": round(random.uniform(0.3, 1.2), 2),
            "bulaniklik": round(random.uniform(0.1, 0.8), 2),
            "iletkenlik": round(random.uniform(280, 480), 1),
            "sicaklik": round(random.uniform(14, 22), 1),
        }
    elif mod == "anomali":
        # Kasıtlı kritik değerler
        return {
            "ph": round(random.choice([random.uniform(5.5, 6.3), random.uniform(8.8, 9.5)]), 2),
            "serbest_klor": round(random.uniform(0.01, 0.08), 3),
            "bulaniklik": round(random.uniform(5.5, 12.0), 2),
            "iletkenlik": round(random.uniform(820, 1100), 1),
            "sicaklik": round(random.uniform(24, 32), 1),
        }
    else:  # karisik
        return _uret_olcum_verileri("anomali" if random.random() < 0.35 else "normal")


@app.get("/api/sim/durum", tags=["Simülasyon"])
async def sim_durum(current_user: models.Kullanici = Depends(require_role(["yonetici"]))):
    """Simülatörün toplam tetikleme sayısını ve son ölçüm bilgisini döner."""
    return {
        "toplam_tetikleme": _sim_durum["toplam"],
        "son_tetikle": _sim_durum["son_tetikle"],
        "son_istasyon_id": _sim_durum["son_istasyon_id"],
    }


@app.post("/api/sim/tetikle", response_model=schemas.SuOlcumuResponse, tags=["Simülasyon"])
async def sim_tetikle(
    background_tasks: BackgroundTasks,
    istasyon_id: int = 1,
    mod: str = "karisik",
    db: AsyncSession = Depends(get_db),
    current_user: models.Kullanici = Depends(require_role(["yonetici"])),
):
    """
    Belirtilen istasyon için tek simüle ölçüm anında kaydeder.
    mod: 'normal' | 'anomali' | 'karisik'
    """
    # İstasyon var mı?
    result = await db.execute(select(models.Istasyon).filter(models.Istasyon.id == istasyon_id))
    istasyon = result.scalars().first()
    if not istasyon:
        raise HTTPException(status_code=404, detail=f"İstasyon (id={istasyon_id}) bulunamadı")

    veriler = _uret_olcum_verileri(mod)
    db_olcum = models.SuOlcumu(
        istasyon_id=istasyon_id, personel_notu=f"[SIM:{mod.upper()}] Otomatik simülasyon ölçümü", **veriler
    )
    db.add(db_olcum)
    await db.commit()
    await db.refresh(db_olcum)

    # Kural motoru
    analiz_girdisi = _olcum_to_analiz_girdisi(db_olcum)
    kural_motoru_sonucu = await hesapla_anomali_durumu(db, analiz_girdisi)
    db_olcum.risk_seviyesi = kural_motoru_sonucu.get("en_yuksek_risk_seviyesi", "NORMAL")
    await db.commit()
    await db.refresh(db_olcum)

    # LLM arka plana
    background_tasks.add_task(arka_planda_analiz_et, db_olcum.id, SessionLocal)

    # Durum güncelle
    _sim_durum["toplam"] += 1
    _sim_durum["son_tetikle"] = _dt.datetime.now(_dt.timezone.utc).isoformat()
    _sim_durum["son_istasyon_id"] = istasyon_id

    await log_audit(
        db,
        kullanici_id=current_user.id,
        islem_tipi="SIM_OLCUM",
        detay=f"Simülatör tetiklendi — İstasyon {istasyon_id}, Mod: {mod}",
    )

    return await _olcum_to_response(db_olcum, analiz_sonucu=kural_motoru_sonucu)


# ---------------------------------------------------------------------------
# LLM Endpoint'i (eski — geriye dönük uyumluluk için korundu)
# ---------------------------------------------------------------------------


@app.get(
    "/olcumler/{olcum_id}/aksiyon-onerisi",
    response_model=schemas.AksiyonOneriResponse,
    tags=["LLM — Aksiyon Önerisi (Eski)"],
    deprecated=True,
)
@app.get(
    "/su-olcumu/{id}/aksiyon-onerisi",
    tags=["LLM — Aksiyon Önerisi (Aşama 3)"],
)
async def get_su_olcumu_aksiyon_onerisi(id: int, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    """
    Ölçüm için anomali raporu çıkarır ve LLM üzerinden teknik aksiyon önerisi döndürür.
    """
    from app.llm_service import olustur_teknik_aksiyon_onerisi

    result = await db.execute(select(models.SuOlcumu).filter(models.SuOlcumu.id == id))
    olcum = result.scalars().first()
    if not olcum:
        raise HTTPException(status_code=404, detail="Ölçüm bulunamadı")

    analiz_girdisi = _olcum_to_analiz_girdisi(olcum)
    kural_motoru_sonucu = await hesapla_anomali_durumu(db, analiz_girdisi)

    teknik_oneri, llm_durumu = await olustur_teknik_aksiyon_onerisi(
        olcum_id=id, anomali_raporu=kural_motoru_sonucu, db=db
    )

    # 4. Faz: LLM-as-a-Judge kalite kontrolünü arka plana at (Sıfır gecikme)
    from app.judge_service import degerlendir_llm_ciktisi

    background_tasks.add_task(degerlendir_llm_ciktisi, id, kural_motoru_sonucu, teknik_oneri, SessionLocal)

    return {"olcum_id": id, "aksiyon_onerisi": teknik_oneri, "llm_durumu": llm_durumu}
