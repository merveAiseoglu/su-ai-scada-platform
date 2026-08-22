import uuid
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import validates
from sqlalchemy.sql import func

from app.database import Base
from app.validators import kural_mantigi_gecerli_mi

class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String, nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Istasyon(Base):
    __tablename__ = "istasyonlar"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Uuid, ForeignKey("organizations.id"), nullable=False)
    ad = Column(String, index=True, nullable=False)
    konum = Column(String, nullable=True)
    tip = Column(String, nullable=False)  # örn: "Kuyu", "Depo", "Şebeke"
    aktif_mi = Column(Boolean, default=True)
    enlem = Column(Float, nullable=True)
    boylam = Column(Float, nullable=True)


class SuOlcumu(Base):
    __tablename__ = "su_olcumleri"

    id = Column(Integer, primary_key=True, index=True)
    istasyon_id = Column(Integer, ForeignKey("istasyonlar.id"), nullable=False)
    ph = Column(Float, nullable=True)
    serbest_klor = Column(Float, nullable=True)
    bulaniklik = Column(Float, nullable=True)
    iletkenlik = Column(Float, nullable=True)
    sicaklik = Column(Float, nullable=True)
    olcum_tarihi = Column(DateTime(timezone=True), server_default=func.now())
    personel_notu = Column(Text, nullable=True)
    # --- Asenkron analiz alanları ---
    analiz_durumu = Column(String, default="BEKLİYOR", nullable=False, server_default="BEKLİYOR")
    risk_seviyesi = Column(String, nullable=True)  # Kural motorundan: NORMAL / DÜŞÜK / ORTA / KRİTİK
    aksiyon_onerisi = Column(Text, nullable=True)  # LLM narratörden dönen teknik öneri metni

    # --- Predictive Analiz (Time-Series) ---
    trend_risk_score = Column(Integer, nullable=True, default=None)
    trend_direction = Column(String, nullable=True, default=None)
    projected_value = Column(Float, nullable=True, default=None)
    projection_message = Column(String, nullable=True, default=None)

    # Migration: alembic/versions/47ab31706e6f_add_predictive_engine_columns.py


class EsikDegeri(Base):
    __tablename__ = "esik_degerleri"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Uuid, ForeignKey("organizations.id"), nullable=False)
    parametre_adi = Column(String, index=True, nullable=False)  # örn: "ph", "serbest_klor"
    min_deger = Column(Float, nullable=True)
    max_deger = Column(Float, nullable=True)
    birim = Column(String, nullable=False)
    kaynak_url = Column(String, nullable=True)

    __table_args__ = (
        UniqueConstraint("organization_id", "parametre_adi", name="uq_esik_org_param"),
    )


class AnomaliKurali(Base):
    __tablename__ = "anomali_kurallari"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Uuid, ForeignKey("organizations.id"), nullable=False)
    kural_adi = Column(String, nullable=False)
    kural_mantigi = Column(
        Text, nullable=False
    )  # Python'da eval() ile çalıştırılabilecek format: "ph < 6.5 or ph > 9.5"
    risk_seviyesi = Column(String, nullable=False)  # "DÜŞÜK", "ORTA", "KRİTİK"
    saha_uyarisi = Column(Text, nullable=False)

    @validates("kural_mantigi")
    def validate_kural_mantigi(self, key, value):
        gecerli, hata = kural_mantigi_gecerli_mi(value)
        if not gecerli:
            raise ValueError(f"Geçersiz kural mantığı syntax'ı: {hata}")
        return value


class AnalizMetrikleri(Base):
    """
    LLM-as-a-Judge değerlendirme sonuçları.
    Her ölçüme 1:1 bağlıdır; ölçüm silinince otomatik silinir (CASCADE).
    """

    __tablename__ = "analiz_metrikleri"

    id = Column(Integer, primary_key=True, index=True)
    olcum_id = Column(
        Integer,
        ForeignKey("su_olcumleri.id", ondelete="CASCADE"),
        unique=True,  # Bir ölçüme en fazla bir metrik kaydı
        nullable=False,
        index=True,
    )
    llm_onerisi = Column(Text, nullable=True)  # Yargıca gönderilen orijinal öneri
    uygunluk_puani = Column(Integer, nullable=False)  # 0–100 arası
    degerlendirme_notu = Column(Text, nullable=False)  # Halüsinasyon vs. açıklaması
    prompt_version = Column(String, nullable=True)  # e.g., "v1"
    llm_provider = Column(String, nullable=True)  # e.g., "openai" or "ollama"
    istasyon_id = Column(Integer, ForeignKey("istasyonlar.id", ondelete="CASCADE"), nullable=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())


class Kullanici(Base):
    __tablename__ = "kullanicilar"
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Uuid, ForeignKey("organizations.id"), nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    sifre_hash = Column(String, nullable=False)
    rol = Column(String, nullable=False, default="saha_personeli")  # 'saha_personeli' or 'yonetici'
    aktif_mi = Column(Boolean, default=True)

    # Notifications
    push_token = Column(String, nullable=True)
    notify_push = Column(Boolean, default=True)
    notify_email = Column(Boolean, default=True)

    # TODO(Migration): For existing databases without Alembic, run the following SQL manually:
    # ALTER TABLE kullanicilar ADD COLUMN push_token VARCHAR;
    # ALTER TABLE kullanicilar ADD COLUMN notify_push BOOLEAN DEFAULT TRUE;
    # ALTER TABLE kullanicilar ADD COLUMN notify_email BOOLEAN DEFAULT TRUE;


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    kullanici_id = Column(Integer, ForeignKey("kullanicilar.id"), nullable=True)
    islem_tipi = Column(String, nullable=False)  # e.g., 'LOGIN', 'OLCUM_EKLENDI', 'AYAR_DEGISTIRILDI'
    detay = Column(Text, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())


class TokenBlocklist(Base):
    """
    Store revoked JWT IDs (jti) to blacklist tokens upon logout.
    """

    __tablename__ = "token_blocklist"
    id = Column(Integer, primary_key=True, index=True)
    jti = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
