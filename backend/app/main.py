# app/main.py  —  Su-AI API v4.0  (Asenkron LLM + BackgroundTasks)
import datetime as _dt
import os
import random
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import List

import calendar
import jwt
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, Response, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from prometheus_fastapi_instrumentator import Instrumentator, metrics
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app import models, schemas
from app.auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    ALGORITHM,
    SECRET_KEY,
    create_access_token,
    create_refresh_token,
    log_audit,
    oauth2_scheme,
    require_role,
    verify_password,
)
from app.database import DEV_DROP_RECREATE, SessionLocal, engine, get_db
from app.engine import hesapla_anomali_durumu
from app.llm_service import arka_planda_analiz_et
from app.metrics import anomaly_counter, trend_risk_histogram
from app.predictive_engine import analyze_trend
from app.report_service import generate_monthly_pdf_report
from app.tasks import fire_and_forget
from app.validators import kural_mantigi_gecerli_mi

SEVERITY_MAP = {
    "NORMAL": "normal",
    "DÜŞÜK": "dusuk",
    "ORTA": "orta",
    "KRİTİK": "kritik",
}


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

        # Varsayılan Organizasyon (SUSKİ) oluştur (Eğer yoksa)
        import uuid
        org_result = await conn.execute(select(models.Organization).filter(models.Organization.name == "SUSKİ Genel Müdürlüğü"))
        org = org_result.fetchone()
        if not org:
            default_org_id = uuid.uuid4()
            await conn.execute(
                models.Organization.__table__.insert().values(
                    id=default_org_id,
                    name="SUSKİ Genel Müdürlüğü"
                )
            )
            print("[OK] Varsayilan organizasyon (SUSKİ) eklendi.")
        else:
            default_org_id = org[0]

        # Admin kullanicisi olustur (Eger yoksa)
        result = await conn.execute(select(models.Kullanici).filter(models.Kullanici.email == "admin@suski.gov.tr"))
        admin = result.fetchone()
        if not admin:
            from app.auth import get_password_hash

            await conn.execute(
                models.Kullanici.__table__.insert().values(
                    email="admin@suski.gov.tr",
                    sifre_hash=get_password_hash("admin123"),
                    rol="yonetici",
                    aktif_mi=True,
                    organization_id=default_org_id,
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
                    [
                        {
                            "email": "personel1@suski.gov.tr",
                            "sifre_hash": get_password_hash("pers123"),
                            "rol": "saha_personeli",
                            "aktif_mi": True,
                            "organization_id": default_org_id,
                        },
                        {
                            "email": "personel@suski.gov.tr",
                            "sifre_hash": get_password_hash("pers123"),
                            "rol": "saha_personeli",
                            "aktif_mi": True,
                            "organization_id": default_org_id,
                        },
                    ]
                )
            )
            print("[OK] Varsayilan personel hesaplari eklendi.")

        # Ornek Istasyonlar
        ist_result = await conn.execute(select(models.Istasyon).filter(models.Istasyon.ad == "Merkez Su Deposu"))
        if not ist_result.fetchone():
            await conn.execute(
                models.Istasyon.__table__.insert().values(
                    [
                        {
                            "organization_id": default_org_id,
                            "ad": "Merkez Su Deposu",
                            "konum": "Şanlıurfa Merkez",
                            "tip": "Depo",
                            "enlem": 37.1674,
                            "boylam": 38.7955,
                            "aktif_mi": True,
                        },
                        {
                            "organization_id": default_org_id,
                            "ad": "Karaköprü Kuyusu",
                            "konum": "Karaköprü",
                            "tip": "Kuyu",
                            "enlem": 37.1901,
                            "boylam": 38.7885,
                            "aktif_mi": True,
                        },
                        {
                            "organization_id": default_org_id,
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

    from app.mqtt_client import get_mqtt_client

    app.state.mqtt_client = get_mqtt_client()
    if app.state.mqtt_client:
        app.state.mqtt_client.loop_start()

    yield

    if getattr(app.state, "mqtt_client", None):
        app.state.mqtt_client.loop_stop()
        app.state.mqtt_client.disconnect()


# ---------------------------------------------------------------------------
# FastAPI uygulaması
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Su-AI API",
    description="Şanlıurfa Su İşleri — Su Kalitesi İzleme ve Karar Destek Sistemi",
    version="4.0.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Reports Endpoint
# ---------------------------------------------------------------------------
@app.get("/admin/reports/monthly", tags=["Admin Reports"])
async def get_monthly_report(
    month: str = Query(None, description="Format YYYY-MM. Defaults to current month."),
    db: AsyncSession = Depends(get_db),
    current_user: models.Kullanici = Depends(require_role(["yonetici"]))
):
    if month is None:
        month = _dt.datetime.now().strftime("%Y-%m")
        
    try:
        year_str, month_str = month.split("-")
        year_int, month_int = int(year_str), int(month_str)
        # Determine start and end of month
        _, last_day = calendar.monthrange(year_int, month_int)
        start_date = _dt.datetime(year_int, month_int, 1)
        end_date = _dt.datetime(year_int, month_int, last_day, 23, 59, 59)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid month format. Use YYYY-MM")
        
    from sqlalchemy import func
    
    stations_result = await db.execute(select(models.Istasyon).filter(models.Istasyon.organization_id == current_user.organization_id))
    stations = stations_result.scalars().all()
    station_ids = [st.id for st in stations]
    if not station_ids:
        return Response(content=b"", media_type="application/pdf")
    
    stmt_total = (
        select(models.SuOlcumu.istasyon_id, func.count(models.SuOlcumu.id))
        .filter(models.SuOlcumu.istasyon_id.in_(station_ids))
        .filter(models.SuOlcumu.olcum_tarihi >= start_date)
        .filter(models.SuOlcumu.olcum_tarihi <= end_date)
        .group_by(models.SuOlcumu.istasyon_id)
    )
    res_total = await db.execute(stmt_total)
    totals_map = dict(res_total.all())
    
    stmt_anom = (
        select(models.SuOlcumu.istasyon_id, func.count(models.SuOlcumu.id))
        .filter(models.SuOlcumu.istasyon_id.in_(station_ids))
        .filter(models.SuOlcumu.olcum_tarihi >= start_date)
        .filter(models.SuOlcumu.olcum_tarihi <= end_date)
        .filter(models.SuOlcumu.risk_seviyesi.in_(["DÜŞÜK", "ORTA", "KRİTİK"]))
        .group_by(models.SuOlcumu.istasyon_id)
    )
    res_anom = await db.execute(stmt_anom)
    anoms_map = dict(res_anom.all())
    
    station_stats = []
    for st in stations:
        t_count = totals_map.get(st.id, 0)
        if t_count > 0:
            a_count = anoms_map.get(st.id, 0)
            rate = (a_count / t_count) * 100
            station_stats.append({
                "station_name": st.ad,
                "total_measurements": t_count,
                "anomaly_count": a_count,
                "anomaly_rate": rate
            })
            
    stmt_judge = (
        select(func.avg(models.AnalizMetrikleri.uygunluk_puani))
        .join(models.SuOlcumu, models.AnalizMetrikleri.olcum_id == models.SuOlcumu.id)
        .filter(models.SuOlcumu.istasyon_id.in_(station_ids))
        .filter(models.SuOlcumu.olcum_tarihi >= start_date)
        .filter(models.SuOlcumu.olcum_tarihi <= end_date)
    )
    res_judge = await db.execute(stmt_judge)
    judge_score_avg = res_judge.scalar()
    if judge_score_avg is not None:
        judge_score_avg = float(judge_score_avg)
        
    pdf_bytes = generate_monthly_pdf_report(month, station_stats, judge_score_avg)
    
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="report_{month}.pdf"'
        }
    )

# Prometheus auto-instrumentation
instrumentator = Instrumentator()
instrumentator.add(
    metrics.latency(buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0))
)
instrumentator.instrument(app).expose(app)

limiter = Limiter(key_func=get_remote_address, default_limits=[os.getenv("GLOBAL_RATE_LIMIT", "100/minute")])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "").split(",") if os.getenv("ALLOWED_ORIGINS") else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Cross-Origin-Resource-Policy"] = "same-site"
    return response


# ---------------------------------------------------------------------------
# Yardımcı fonksiyonlar
# ---------------------------------------------------------------------------


def _olcum_to_analiz_girdisi(olcum: models.SuOlcumu) -> dict:
    """SuOlcumu DB nesnesini kural motoru için dict'e çevirir (istasyon_id dahil)."""
    return {
        "istasyon_id": olcum.istasyon_id,
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


@app.get("/health", tags=["Genel"])
async def health_check(db: AsyncSession = Depends(get_db)):
    status = {"db": "ok", "chromadb": "ok", "ollama": "ok"}
    try:
        # DB check
        await db.execute(select(1))
    except Exception:
        status["db"] = "degraded"

    try:
        # ChromaDB check
        from app.rag_service import get_client

        get_client().heartbeat()
    except Exception:
        status["chromadb"] = "degraded"

    try:
        # Ollama check (reachability via basic HTTP)
        import httpx

        host = os.getenv("OLLAMA_HOST", "ollama")
        port = os.getenv("OLLAMA_PORT", "11434")
        async with httpx.AsyncClient(timeout=2) as client:
            await client.get(f"http://{host}:{port}/")
    except Exception:
        status["ollama"] = "degraded"

    return status


# ---------------------------------------------------------------------------
# Kimlik Doğrulama Endpoint'i
# ---------------------------------------------------------------------------


@app.post("/token", response_model=schemas.Token, tags=["Kimlik Doğrulama"])
@limiter.limit(os.getenv("AUTH_RATE_LIMIT", "5/minute"))
async def login_for_access_token(
    request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(models.Kullanici).filter(models.Kullanici.email == form_data.username))
    user = result.scalars().first()

    if not user or not verify_password(form_data.password, user.sifre_hash):
        raise HTTPException(status_code=401, detail="Hatalı e-posta veya şifre", headers={"WWW-Authenticate": "Bearer"})

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": user.email, "rol": user.rol}, expires_delta=access_token_expires)

    refresh_token = create_refresh_token(data={"sub": user.email, "rol": user.rol})

    # Audit log
    await log_audit(db, kullanici_id=user.id, islem_tipi="LOGIN", detay="Kullanıcı sisteme giriş yaptı.")

    return {"access_token": access_token, "token_type": "bearer", "refresh_token": refresh_token}


@app.post("/logout", tags=["Kimlik Doğrulama"])
async def logout(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    from sqlalchemy.exc import IntegrityError
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        jti = payload.get("jti")
        if jti:
            blacklisted_token = models.TokenBlocklist(jti=jti)
            db.add(blacklisted_token)
            await db.commit()
    except IntegrityError:
        # Token is already blacklisted
        await db.rollback()
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Geçersiz token")
    return {"mesaj": "Başarıyla çıkış yapıldı"}


@app.post("/refresh", response_model=schemas.Token, tags=["Kimlik Doğrulama"])
@limiter.limit(os.getenv("AUTH_RATE_LIMIT", "5/minute"))
async def refresh_token(request: Request, body: schemas.RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    credentials_exception = HTTPException(status_code=401, detail="Geçersiz refresh token")
    try:
        payload = jwt.decode(body.refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            raise credentials_exception

        jti = payload.get("jti")
        if jti:
            blacklisted = await db.execute(select(models.TokenBlocklist).filter(models.TokenBlocklist.jti == jti))
            if blacklisted.scalars().first():
                raise credentials_exception

        email: str = payload.get("sub")
        rol: str = payload.get("rol")
        if email is None:
            raise credentials_exception

        new_access_token = create_access_token(data={"sub": email, "rol": rol})
        new_refresh_token = create_refresh_token(data={"sub": email, "rol": rol})

        if jti:
            db.add(models.TokenBlocklist(jti=jti))
            await db.commit()

        return {"access_token": new_access_token, "token_type": "bearer", "refresh_token": new_refresh_token}
    except jwt.PyJWTError as err:
        raise credentials_exception from err


# ---------------------------------------------------------------------------
# LLMOps Dashboard Endpoint (Yönetici Özel)
# ---------------------------------------------------------------------------


@app.get("/admin/llmops/dashboard", response_model=schemas.LLMOpsDashboardResponse, tags=["LLMOps"])
async def get_llmops_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: models.Kullanici = Depends(require_role(["yonetici"])),
):
    """
    LLM-as-a-Judge analiz metriklerini döner.
    Prompt versiyonları ve LLM sağlayıcılarına göre A/B testi ve başarı kırılımını içerir.
    """
    from sqlalchemy.future import select
    from sqlalchemy.sql import func

    # 1. Genel Ortalama ve Toplam
    overall_result = await db.execute(
        select(func.avg(models.AnalizMetrikleri.uygunluk_puani), func.count(models.AnalizMetrikleri.id))
    )
    overall_avg, total_evals = overall_result.first()
    overall_avg = float(overall_avg) if overall_avg else 0.0
    total_evals = total_evals or 0

    # 2. Prompt Versiyonuna Göre
    prompt_result = await db.execute(
        select(
            models.AnalizMetrikleri.prompt_version,
            func.avg(models.AnalizMetrikleri.uygunluk_puani),
            func.count(models.AnalizMetrikleri.id),
        ).group_by(models.AnalizMetrikleri.prompt_version)
    )
    by_prompt = []
    for row in prompt_result.all():
        by_prompt.append(
            {"prompt_version": row[0] or "unknown", "avg_score": float(row[1]) if row[1] else 0.0, "count": row[2]}
        )

    # 3. LLM Sağlayıcısına Göre
    provider_result = await db.execute(
        select(
            models.AnalizMetrikleri.llm_provider,
            func.avg(models.AnalizMetrikleri.uygunluk_puani),
            func.count(models.AnalizMetrikleri.id),
        ).group_by(models.AnalizMetrikleri.llm_provider)
    )
    by_provider = []
    for row in provider_result.all():
        by_provider.append(
            {"llm_provider": row[0] or "unknown", "avg_score": float(row[1]) if row[1] else 0.0, "count": row[2]}
        )

    # 4. En düşük puanlı 5 analiz
    lowest_result = await db.execute(
        select(models.AnalizMetrikleri).order_by(models.AnalizMetrikleri.uygunluk_puani.asc()).limit(5)
    )
    lowest_scores = lowest_result.scalars().all()

    return {
        "overall_avg_score": overall_avg,
        "total_evaluations": total_evals,
        "by_prompt_version": by_prompt,
        "by_provider": by_provider,
        "lowest_scores": lowest_scores,
    }


# ---------------------------------------------------------------------------
# Kullanıcı Ayarları Endpoint'leri
# ---------------------------------------------------------------------------


@app.post("/admin/users/{user_id}/push-token", tags=["Kullanıcı Ayarları"])
async def update_push_token(
    user_id: int,
    body: schemas.PushTokenUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: models.Kullanici = Depends(require_role(["yonetici"])),
):
    result = await db.execute(
        select(models.Kullanici)
        .filter(models.Kullanici.id == user_id, models.Kullanici.organization_id == current_user.organization_id)
    )
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")
    user.push_token = body.push_token
    await db.commit()
    return {"mesaj": "Push token güncellendi"}


@app.patch("/admin/users/{user_id}/notification-preferences", tags=["Kullanıcı Ayarları"])
async def update_notification_preferences(
    user_id: int,
    body: schemas.NotificationPreferencesUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: models.Kullanici = Depends(require_role(["yonetici"])),
):
    result = await db.execute(
        select(models.Kullanici)
        .filter(models.Kullanici.id == user_id, models.Kullanici.organization_id == current_user.organization_id)
    )
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")

    if body.notify_push is not None:
        user.notify_push = body.notify_push
    if body.notify_email is not None:
        user.notify_email = body.notify_email

    await db.commit()
    return {"mesaj": "Bildirim tercihleri güncellendi"}


# ---------------------------------------------------------------------------
# İstasyon Endpoint'leri
# ---------------------------------------------------------------------------


@app.post("/istasyonlar/", response_model=schemas.IstasyonResponse, tags=["İstasyonlar"])
async def create_istasyon(
    istasyon: schemas.IstasyonCreate,
    db: AsyncSession = Depends(get_db),
    current_user: models.Kullanici = Depends(require_role(["yonetici"])),
):
    db_istasyon = models.Istasyon(**istasyon.model_dump(), organization_id=current_user.organization_id)
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
    result = await db.execute(
        select(models.Istasyon)
        .filter(models.Istasyon.organization_id == current_user.organization_id)
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


@app.get("/istasyonlar/{istasyon_id}", response_model=schemas.IstasyonResponse, tags=["İstasyonlar"])
async def read_istasyon(
    istasyon_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.Kullanici = Depends(require_role(["saha_personeli", "yonetici"])),
):
    result = await db.execute(
        select(models.Istasyon)
        .filter(models.Istasyon.id == istasyon_id, models.Istasyon.organization_id == current_user.organization_id)
    )
    istasyon = result.scalars().first()
    if not istasyon:
        raise HTTPException(status_code=404, detail="İstasyon bulunamadı")
    return istasyon


# ---------------------------------------------------------------------------
# GIS / Harita Endpoint'leri
# ---------------------------------------------------------------------------
# MOBILE APP MAP VIEW INTEGRATION:
# The mobile app should read `trend_risk_score` from the recent measurements
# (or the GIS endpoint response, once added there).
# Use amber markers for a score between 40-70.
# Use red markers for a hard anomaly (risk_seviyesi == "KRİTİK") or score > 70.


@app.get("/api/gis/istasyonlar", response_model=List[schemas.GisIstasyonResponse], tags=["GIS"])
async def get_gis_istasyonlar(
    db: AsyncSession = Depends(get_db),
    current_user: models.Kullanici = Depends(require_role(["saha_personeli", "yonetici"])),
):
    result = await db.execute(
        select(models.Istasyon)
        .filter(models.Istasyon.aktif_mi.is_(True), models.Istasyon.organization_id == current_user.organization_id)
    )
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


async def _apply_predictive_engine(db: AsyncSession, db_olcum: models.SuOlcumu):
    """
    Kural motoru sonrası, LLM narrator öncesi predictive trend analizi yapar.
    Son 10 ölçümü alır, en yüksek risk skorunu hesaplar ve db_olcum üzerine kaydeder.
    """
    from sqlalchemy.future import select

    from app import models

    q = (
        select(models.SuOlcumu)
        .filter(models.SuOlcumu.istasyon_id == db_olcum.istasyon_id, models.SuOlcumu.id != db_olcum.id)
        .order_by(models.SuOlcumu.olcum_tarihi.desc())
        .limit(9)
    )
    result = await db.execute(q)
    past_measurements = result.scalars().all()

    # Kronolojik sıra (eski -> yeni) ve mevcut ölçümü ekle
    past_measurements = list(reversed(past_measurements))
    past_measurements.append(db_olcum)

    worst_score = -1
    best_result = None

    import asyncio

    for param in ["ph", "serbest_klor", "bulaniklik"]:
        values = [getattr(m, param, None) for m in past_measurements]
        if any(v is not None for v in values):
            trend_res = await asyncio.to_thread(analyze_trend, db_olcum.istasyon_id, param, values)
            trend_risk_histogram.labels(parameter=param).observe(trend_res["trend_risk_score"])
            if trend_res["trend_risk_score"] > worst_score:
                worst_score = trend_res["trend_risk_score"]
                best_result = trend_res

    if best_result:
        db_olcum.trend_risk_score = best_result["trend_risk_score"]
        db_olcum.trend_direction = best_result["trend_direction"]
        db_olcum.projected_value = best_result["projected_value"]
        db_olcum.projection_message = best_result["projection_message"]

    return db_olcum


@app.get("/admin/trend-analysis/{istasyon_id}", response_model=schemas.TrendAnalysisResponse, tags=["Admin"])
async def get_trend_analysis(
    istasyon_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.Kullanici = Depends(require_role(["yonetici"])),
):
    """
    Admin-only endpoint to get the last 10 measurements and their trend logic.
    """
    from sqlalchemy.future import select

    from app import models

    q = (
        select(models.SuOlcumu)
        .join(models.Istasyon, models.Istasyon.id == models.SuOlcumu.istasyon_id)
        .filter(models.SuOlcumu.istasyon_id == istasyon_id)
        .filter(models.Istasyon.organization_id == current_user.organization_id)
        .order_by(models.SuOlcumu.olcum_tarihi.desc())
        .limit(10)
    )
    result = await db.execute(q)
    measurements = result.scalars().all()
    # Önceden predictive_engine tarafından hesaplanıp DB'ye yazılan ancak response'a dahil edilmeyen
    # projected_value ve projection_message alanları artık response'a dahil edilerek istemciye ulaştırılıyor.
    return {
        "istasyon_id": istasyon_id,
        "measurements": [
            {
                "id": m.id,
                "date": m.olcum_tarihi,
                "trend_risk_score": m.trend_risk_score,
                "trend_direction": m.trend_direction,
                "projected_value": m.projected_value,
                "projection_message": m.projection_message,
            }
            for m in measurements
        ],
    }


@app.get("/olcumler/", response_model=List[schemas.SuOlcumuResponse], tags=["Ölçümler"])
async def list_olcumler(
    istasyon_id: int | None = None,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: models.Kullanici = Depends(require_role(["saha_personeli", "yonetici"])),
):
    """
    Son ölçümleri listeler. Opsiyonel istasyon_id filtresi, limit ve offset parametreleri desteklenir.
    SimulatorScreen, geçmiş listesi ve dashboard için kullanılır.
    """
    q = (
        select(models.SuOlcumu)
        .join(models.Istasyon, models.Istasyon.id == models.SuOlcumu.istasyon_id)
        .filter(models.Istasyon.organization_id == current_user.organization_id)
        .order_by(models.SuOlcumu.olcum_tarihi.desc())
        .offset(offset)
        .limit(limit)
    )
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
    print(f"\n[MOBİL_GELEN_HAM_PAYLOAD] {olcum.model_dump()}")
    result = await db.execute(
        select(models.Istasyon)
        .filter(models.Istasyon.id == olcum.istasyon_id, models.Istasyon.organization_id == current_user.organization_id)
    )
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
    print(f"[KURAL_MOTORU_ANALIZ_GIRDISI] {analiz_girdisi}")
    kural_motoru_sonucu = await hesapla_anomali_durumu(db, analiz_girdisi)

    db_olcum.risk_seviyesi = kural_motoru_sonucu.get("en_yuksek_risk_seviyesi", "NORMAL")
    anomaly_counter.labels(severity=SEVERITY_MAP.get(db_olcum.risk_seviyesi, "normal")).inc()

    await _apply_predictive_engine(db, db_olcum)

    await db.commit()
    await db.refresh(db_olcum)

    # Alert Notifications
    if db_olcum.risk_seviyesi == "KRİTİK":
        from app.notification_service import dispatch_critical_alerts
        fire_and_forget(dispatch_critical_alerts(db_olcum.id, SessionLocal))

    # 4. LLM görevini arka plana at — SessionLocal factory geçilir (thread-safe)
    fire_and_forget(arka_planda_analiz_et(db_olcum.id, SessionLocal))

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
    result = await db.execute(
        select(models.SuOlcumu)
        .join(models.Istasyon, models.Istasyon.id == models.SuOlcumu.istasyon_id)
        .filter(models.SuOlcumu.id == olcum_id, models.Istasyon.organization_id == current_user.organization_id)
    )
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
    Not: Audit log'lar append-only (sadece ekleme) olup, sistem üzerinden silinemez veya güncellenemez.
    Kayıtlar yasal mevzuatlar gereği 2 yıl saklanmalıdır (prodüksiyon öncesi hukuk departmanı ile teyit ediniz).
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
            "serbest_klor": round(random.uniform(0.25, 0.45), 2),
            "bulaniklik": round(random.uniform(0.1, 0.8), 2),
            "iletkenlik": round(random.uniform(280, 380), 1),
            "sicaklik": round(random.uniform(14, 22), 1),
        }
    elif mod == "anomali":
        # Kasıtlı kritik değerler (Kritik eşikler: pH < 6.5 veya > 9.5, klor < 0.1/0.2, bulanıklık > 5.0, iletkenlik > 2000)
        return {
            "ph": round(random.choice([random.uniform(5.0, 6.2), random.uniform(9.6, 10.5)]), 2),
            "serbest_klor": round(random.uniform(0.01, 0.08), 3),
            "bulaniklik": round(random.uniform(5.5, 12.0), 2),
            "iletkenlik": round(random.uniform(2100, 3200), 1),
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


@app.post("/api/sim/tetikle", tags=["Simülasyon"])
async def sim_tetikle(
    request: Request,
    background_tasks: BackgroundTasks,
    istasyon_id: int = 1,
    mod: str = "karisik",
    use_mqtt: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: models.Kullanici = Depends(require_role(["yonetici"])),
):
    """
    Belirtilen istasyon için tek simüle ölçüm anında kaydeder.
    mod: 'normal' | 'anomali' | 'karisik'
    """
    # İstasyon var mı?
    result = await db.execute(
        select(models.Istasyon)
        .filter(models.Istasyon.id == istasyon_id, models.Istasyon.organization_id == current_user.organization_id)
    )
    istasyon = result.scalars().first()
    if not istasyon:
        raise HTTPException(status_code=404, detail=f"İstasyon (id={istasyon_id}) bulunamadı")

    veriler = _uret_olcum_verileri(mod)

    if use_mqtt:
        mqtt_client = getattr(request.app.state, "mqtt_client", None)
        if not mqtt_client:
            raise HTTPException(status_code=500, detail="MQTT istemcisi bağlı değil")

        payload = {
            "station_id": istasyon_id,
            "pH": veriler["ph"],
            "chlorine": veriler["serbest_klor"],
            "turbidity": veriler["bulaniklik"],
            "conductivity": veriler["iletkenlik"],
            "temperature": veriler["sicaklik"],
            "timestamp": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        }
        import json

        topic = f"su-ai/stations/{istasyon_id}/measurements"
        mqtt_client.publish(topic, json.dumps(payload))

        _sim_durum["toplam"] += 1
        _sim_durum["son_tetikle"] = _dt.datetime.now(_dt.timezone.utc).isoformat()
        _sim_durum["son_istasyon_id"] = istasyon_id

        return {"mesaj": f"Veri MQTT ({topic}) üzerinden gönderildi", "payload": payload}

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
    anomaly_counter.labels(severity=SEVERITY_MAP.get(db_olcum.risk_seviyesi, "normal")).inc()

    await _apply_predictive_engine(db, db_olcum)

    await db.commit()
    await db.refresh(db_olcum)

    # Alert Notifications
    if db_olcum.risk_seviyesi == "KRİTİK":
        from app.notification_service import dispatch_critical_alerts
        fire_and_forget(dispatch_critical_alerts(db_olcum.id, SessionLocal))

    # Arka plan LLM/Trend analizi (Bu da ~5-6 sn sürer, async yapıyoruz)
    fire_and_forget(arka_planda_analiz_et(db_olcum.id, SessionLocal))

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
async def get_su_olcumu_aksiyon_onerisi(
    id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: models.Kullanici = Depends(require_role(["saha_personeli", "yonetici"])),
):
    """
    Ölçüm için anomali raporu çıkarır ve LLM üzerinden teknik aksiyon önerisi döndürür.
    """
    from app.llm_service import olustur_teknik_aksiyon_onerisi

    result = await db.execute(
        select(models.SuOlcumu)
        .join(models.Istasyon, models.Istasyon.id == models.SuOlcumu.istasyon_id)
        .filter(models.SuOlcumu.id == id, models.Istasyon.organization_id == current_user.organization_id)
    )
    olcum = result.scalars().first()
    if not olcum:
        raise HTTPException(status_code=404, detail="Ölçüm bulunamadı")

    analiz_girdisi = _olcum_to_analiz_girdisi(olcum)
    kural_motoru_sonucu = await hesapla_anomali_durumu(db, analiz_girdisi)

    teknik_oneri, llm_durumu, provider, benzer_vakalar = await olustur_teknik_aksiyon_onerisi(
        olcum_id=id, anomali_raporu=kural_motoru_sonucu, db=db
    )

    # 4. Faz: LLM-as-a-Judge kalite kontrolünü arka plana at (Sıfır gecikme, RAG benzer_vakalar ile)
    from app.judge_service import degerlendir_llm_ciktisi

    background_tasks.add_task(
        degerlendir_llm_ciktisi,
        id,
        kural_motoru_sonucu,
        teknik_oneri,
        SessionLocal,
        provider,
        olcum.istasyon_id,
        benzer_vakalar,
    )

    return {"olcum_id": id, "aksiyon_onerisi": teknik_oneri, "llm_durumu": llm_durumu}

# ---------------------------------------------------------------------------
# Organization Management Endpoint'leri
# ---------------------------------------------------------------------------

@app.post("/admin/organizations", response_model=schemas.OrganizationResponse, tags=["Yönetici - Organizasyon"])
async def create_organization(
    org_data: schemas.OrganizationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: models.Kullanici = Depends(require_role(["yonetici"])),
):
    """
    Sadece yöneticiler yeni organizasyon (tenant) oluşturabilir.
    """
    db_org = models.Organization(**org_data.model_dump())
    db.add(db_org)
    try:
        await db.commit()
        await db.refresh(db_org)
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Organizasyon oluşturulamadı. Aynı isimde organizasyon olabilir.")
        
    await log_audit(db, kullanici_id=current_user.id, islem_tipi="ORG_OLUSTURULDU", detay=f"Yeni organizasyon eklendi: {org_data.name}")
    return db_org

@app.post("/admin/organizations/{org_id}/users", response_model=schemas.KullaniciResponse, tags=["Yönetici - Organizasyon"])
async def add_user_to_organization(
    org_id: str,
    user_data: schemas.KullaniciCreate,
    db: AsyncSession = Depends(get_db),
    current_user: models.Kullanici = Depends(require_role(["yonetici"])),
):
    """
    Organizasyona yeni bir kullanıcı ekler.
    """
    from app.auth import get_password_hash
    import uuid

    # Organizasyon var mı kontrol et
    try:
        parsed_uuid = uuid.UUID(org_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Geçersiz organizasyon ID")

    result = await db.execute(select(models.Organization).filter(models.Organization.id == parsed_uuid))
    org = result.scalars().first()
    if not org:
        raise HTTPException(status_code=404, detail="Organizasyon bulunamadı")

    db_user = models.Kullanici(
        email=user_data.email,
        sifre_hash=get_password_hash(user_data.sifre),
        rol=user_data.rol,
        aktif_mi=user_data.aktif_mi,
        organization_id=parsed_uuid
    )
    db.add(db_user)
    try:
        await db.commit()
        await db.refresh(db_user)
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Kullanıcı oluşturulamadı. E-posta adresi kullanımda olabilir.")

    await log_audit(db, kullanici_id=current_user.id, islem_tipi="USER_EKLENDI", detay=f"Organizasyona ({org_id}) yeni kullanıcı eklendi: {user_data.email}")
    return db_user


# ---------------------------------------------------------------------------
# Admin - Eşik Değerleri ve Anomali Kuralları Yönetim Endpoint'leri
# ---------------------------------------------------------------------------


@app.get("/api/admin/esikler", response_model=List[schemas.EsikDegeriResponse], tags=["Yönetici - Eşik & Kural Yönetimi"])
async def list_admin_esikler(
    db: AsyncSession = Depends(get_db),
    current_user: models.Kullanici = Depends(require_role(["yonetici"])),
):
    """
    Yöneticinin kendi organizasyonuna ait eşik değerlerini listeler.
    """
    result = await db.execute(
        select(models.EsikDegeri).filter(models.EsikDegeri.organization_id == current_user.organization_id)
    )
    return result.scalars().all()


@app.post("/api/admin/esikler", response_model=schemas.EsikDegeriResponse, tags=["Yönetici - Eşik & Kural Yönetimi"])
async def create_admin_esik(
    esik_data: schemas.EsikDegeriCreate,
    db: AsyncSession = Depends(get_db),
    current_user: models.Kullanici = Depends(require_role(["yonetici"])),
):
    """
    Yöneticinin kendi organizasyonuna yeni bir eşik değeri ekler.
    """
    existing_res = await db.execute(
        select(models.EsikDegeri).filter(
            models.EsikDegeri.organization_id == current_user.organization_id,
            models.EsikDegeri.parametre_adi == esik_data.parametre_adi,
        )
    )
    if existing_res.scalars().first():
        raise HTTPException(
            status_code=400,
            detail=f"'{esik_data.parametre_adi}' parametresi için eşik değeri zaten tanımlı.",
        )

    db_esik = models.EsikDegeri(
        organization_id=current_user.organization_id,
        parametre_adi=esik_data.parametre_adi,
        min_deger=esik_data.min_deger,
        max_deger=esik_data.max_deger,
        birim=esik_data.birim,
        kaynak_url=esik_data.kaynak_url,
    )
    db.add(db_esik)
    await db.commit()
    await db.refresh(db_esik)
    await log_audit(
        db,
        kullanici_id=current_user.id,
        islem_tipi="ESIK_EKLENDI",
        detay=f"Eşik eklendi: {db_esik.parametre_adi}",
    )
    return db_esik


@app.put("/api/admin/esikler/{id}", response_model=schemas.EsikDegeriResponse, tags=["Yönetici - Eşik & Kural Yönetimi"])
async def update_admin_esik(
    id: int,
    esik_data: schemas.EsikDegeriUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: models.Kullanici = Depends(require_role(["yonetici"])),
):
    """
    Yöneticinin kendi organizasyonuna ait bir eşik değerini günceller.
    """
    result = await db.execute(
        select(models.EsikDegeri).filter(
            models.EsikDegeri.id == id,
            models.EsikDegeri.organization_id == current_user.organization_id,
        )
    )
    db_esik = result.scalars().first()
    if not db_esik:
        raise HTTPException(status_code=404, detail="Eşik değeri bulunamadı veya bu işlem için yetkiniz yok.")

    if esik_data.min_deger is not None:
        db_esik.min_deger = esik_data.min_deger
    if esik_data.max_deger is not None:
        db_esik.max_deger = esik_data.max_deger
    if esik_data.birim is not None:
        db_esik.birim = esik_data.birim
    if esik_data.kaynak_url is not None:
        db_esik.kaynak_url = esik_data.kaynak_url

    await db.commit()
    await db.refresh(db_esik)
    await log_audit(
        db,
        kullanici_id=current_user.id,
        islem_tipi="ESIK_GUNCELLENDI",
        detay=f"Eşik güncellendi: {db_esik.parametre_adi} (id={id})",
    )
    return db_esik


@app.get("/api/admin/kurallar", response_model=List[schemas.AnomaliKuraliResponse], tags=["Yönetici - Eşik & Kural Yönetimi"])
async def list_admin_kurallar(
    db: AsyncSession = Depends(get_db),
    current_user: models.Kullanici = Depends(require_role(["yonetici"])),
):
    """
    Yöneticinin kendi organizasyonuna ait anomali kurallarını listeler.
    """
    result = await db.execute(
        select(models.AnomaliKurali).filter(models.AnomaliKurali.organization_id == current_user.organization_id)
    )
    return result.scalars().all()


@app.post("/api/admin/kurallar", response_model=schemas.AnomaliKuraliResponse, tags=["Yönetici - Eşik & Kural Yönetimi"])
async def create_admin_kural(
    kural_data: schemas.AnomaliKuraliCreate,
    db: AsyncSession = Depends(get_db),
    current_user: models.Kullanici = Depends(require_role(["yonetici"])),
):
    """
    Yöneticinin kendi organizasyonuna yeni bir anomali kuralı ekler (Syntax doğrulamalı).
    """
    gecerli, hata = kural_mantigi_gecerli_mi(kural_data.kural_mantigi)
    if not gecerli:
        raise HTTPException(status_code=400, detail=f"Geçersiz kural mantığı syntax'ı: {hata}")

    db_kural = models.AnomaliKurali(
        organization_id=current_user.organization_id,
        kural_adi=kural_data.kural_adi,
        kural_mantigi=kural_data.kural_mantigi,
        risk_seviyesi=kural_data.risk_seviyesi,
        saha_uyarisi=kural_data.saha_uyarisi,
    )
    db.add(db_kural)
    await db.commit()
    await db.refresh(db_kural)
    await log_audit(
        db,
        kullanici_id=current_user.id,
        islem_tipi="KURAL_EKLENDI",
        detay=f"Kural eklendi: {db_kural.kural_adi}",
    )
    return db_kural


@app.put("/api/admin/kurallar/{id}", response_model=schemas.AnomaliKuraliResponse, tags=["Yönetici - Eşik & Kural Yönetimi"])
async def update_admin_kural(
    id: int,
    kural_data: schemas.AnomaliKuraliUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: models.Kullanici = Depends(require_role(["yonetici"])),
):
    """
    Yöneticinin kendi organizasyonuna ait bir anomali kuralını günceller (Syntax doğrulamalı).
    """
    result = await db.execute(
        select(models.AnomaliKurali).filter(
            models.AnomaliKurali.id == id,
            models.AnomaliKurali.organization_id == current_user.organization_id,
        )
    )
    db_kural = result.scalars().first()
    if not db_kural:
        raise HTTPException(status_code=404, detail="Anomali kuralı bulunamadı veya bu işlem için yetkiniz yok.")

    if kural_data.kural_mantigi is not None:
        gecerli, hata = kural_mantigi_gecerli_mi(kural_data.kural_mantigi)
        if not gecerli:
            raise HTTPException(status_code=400, detail=f"Geçersiz kural mantığı syntax'ı: {hata}")
        db_kural.kural_mantigi = kural_data.kural_mantigi

    if kural_data.kural_adi is not None:
        db_kural.kural_adi = kural_data.kural_adi
    if kural_data.risk_seviyesi is not None:
        db_kural.risk_seviyesi = kural_data.risk_seviyesi
    if kural_data.saha_uyarisi is not None:
        db_kural.saha_uyarisi = kural_data.saha_uyarisi

    await db.commit()
    await db.refresh(db_kural)
    await log_audit(
        db,
        kullanici_id=current_user.id,
        islem_tipi="KURAL_GUNCELLENDI",
        detay=f"Kural güncellendi: {db_kural.kural_adi} (id={id})",
    )
    return db_kural

