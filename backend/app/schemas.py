from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

# ---------------------------------------------------------------------------
# İstasyon Şemaları
# ---------------------------------------------------------------------------
class IstasyonBase(BaseModel):
    ad: str
    konum: Optional[str] = None
    tip: str
    aktif_mi: bool = True
    enlem: Optional[float] = None
    boylam: Optional[float] = None

class IstasyonCreate(IstasyonBase):
    pass

class IstasyonResponse(IstasyonBase):
    id: int

    class Config:
        from_attributes = True

class GisIstasyonResponse(IstasyonResponse):
    son_olcum_tarihi: Optional[datetime] = None
    son_risk_seviyesi: Optional[str] = None
    son_personel_notu: Optional[str] = None
    # Son ölçüm sensör değerleri (harita callout için)
    son_ph: Optional[float] = None
    son_serbest_klor: Optional[float] = None
    son_bulaniklik: Optional[float] = None
    son_iletkenlik: Optional[float] = None
    son_sicaklik: Optional[float] = None
    son_analiz_durumu: Optional[str] = None
    son_olcum_id: Optional[int] = None   # ResultScreen navigasyonu için

    model_config = ConfigDict(from_attributes=True)

# ---------------------------------------------------------------------------
# Ölçüm Şemaları
# ---------------------------------------------------------------------------

class AnalizMetrikleriResponse(BaseModel):
    uygunluk_puani: int
    degerlendirme_notu: str
    llm_onerisi: Optional[str] = None

    class Config:
        from_attributes = True

class SuOlcumuBase(BaseModel):
    istasyon_id: int
    ph: Optional[float] = None
    serbest_klor: Optional[float] = None
    bulaniklik: Optional[float] = None
    iletkenlik: Optional[float] = None
    sicaklik: Optional[float] = None
    personel_notu: Optional[str] = None

class SuOlcumuCreate(SuOlcumuBase):
    pass

class SuOlcumuResponse(SuOlcumuBase):
    id: int
    olcum_tarihi: datetime
    
    # Asenkron alanlar
    analiz_durumu: str
    risk_seviyesi: Optional[str] = None
    aksiyon_onerisi: Optional[str] = None

    # İsteğe bağlı, kural motorundan dönen veya DB'den çekilen detaylar
    analiz_sonucu: Optional[dict] = None
    metrikler: Optional[AnalizMetrikleriResponse] = None

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# (Eski) LLM Şemaları
# ---------------------------------------------------------------------------
class AksiyonOneriResponse(BaseModel):
    olcum_id: int
    aksiyon_onerisi: str
    llm_durumu: str

# ---------------------------------------------------------------------------
# Kimlik Doğrulama (Auth) Şemaları
# ---------------------------------------------------------------------------

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None
    rol: Optional[str] = None

class KullaniciBase(BaseModel):
    email: str
    rol: str = "saha_personeli"
    aktif_mi: bool = True

class KullaniciCreate(KullaniciBase):
    sifre: str

class KullaniciResponse(KullaniciBase):
    id: int

    model_config = ConfigDict(from_attributes=True)

# ---------------------------------------------------------------------------
# Audit Log Şemaları
# ---------------------------------------------------------------------------

class AuditLogResponse(BaseModel):
    id: int
    kullanici_id: Optional[int]
    islem_tipi: str
    detay: Optional[str]
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)
