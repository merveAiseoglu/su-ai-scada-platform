# Staj Defteri — Kod Parcalari

---

## GUN 1

```yaml
﻿
networks:
  su-ai-network:
    driver: bridge

volumes:
  postgres_data:
  chroma_data:
  ollama_model_cache:
  prometheus_data:
  grafana_data:
  mosquitto_data:
  mosquitto_log:
services:
  # --- Core Services ---
  postgres:
    image: postgres:15
    container_name: su-ai-postgres
    command: postgres -c max_connections=250
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-postgres}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-postgres}
      POSTGRES_DB: ${POSTGRES_DB:-su_ai}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - su-ai-network
    ports:
      - "5432:5432"
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-postgres} -d ${POSTGRES_DB:-su_ai}"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s

  chromadb:
    image: chromadb/chroma:latest
    container_name: su-ai-chromadb
    volumes:
      - chroma_data:/chroma/chroma
    environment:
      - IS_PERSISTENT=TRUE
    networks:
      - su-ai-network
    ports:
      - "8000:8000"
    restart: unless-stopped

  ollama:
    image: ollama/ollama:latest
    container_name: su-ai-ollama
    volumes:
      - ollama_model_cache:/root/.ollama
    networks:
      - su-ai-network
    ports:
      - "11434:11434"
    restart: unless-stopped

  backend:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: su-ai-backend
    volumes:
      - ./backend:/app
    environment:
      - DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER:-postgres}:${POSTGRES_PASSWORD:-postgres}@postgres:5432/${POSTGRES_DB:-su_ai}
      - CHROMA_HOST=${CHROMA_HOST:-chromadb}
      - CHROMA_PORT=${CHROMA_PORT:-8000}
      - OLLAMA_HOST=${OLLAMA_HOST:-ollama}
      - OLLAMA_PORT=${OLLAMA_PORT:-11434}
    env_file:
      - .env
    networks:
      - su-ai-network
    ports:
      - "8080:8000" # Mapped to 8080 to avoid conflict with ChromaDB on host
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 2G
    depends_on:
      postgres:
        condition: service_healthy
      chromadb:
        condition: service_started
      ollama:
        condition: service_started
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/docs')"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 20s

  # --- Observability (Phase 1) ---
  prometheus:
    image: prom/prometheus:latest
    container_name: su-ai-prometheus
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    networks:
      - su-ai-network
    ports:
      - "9090:9090"
    restart: unless-stopped

  grafana:
    image: grafana/grafana:latest
    container_name: su-ai-grafana
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana/provisioning:/etc/grafana/provisioning
      - ./grafana/dashboards:/var/lib/grafana/dashboards
    environment:
      - GF_SECURITY_ADMIN_USER=${GRAFANA_ADMIN_USER:-admin}
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD:-admin}
    networks:
      - su-ai-network
    ports:
      - "3000:3000"
    restart: unless-stopped
    depends_on:
      - prometheus
      
  # --- IoT/MQTT (Phase 6) ---
  mosquitto:
    image: eclipse-mosquitto:2
    container_name: su-ai-mosquitto
    volumes:
      - ./mosquitto/mosquitto.conf:/mosquitto/config/mosquitto.conf
      - mosquitto_data:/mosquitto/data
      - mosquitto_log:/mosquitto/log
    ports:
      - "1883:1883"
    networks:
      - su-ai-network
    restart: unless-stopped
```

Kaynak: `docker-compose.yml` (satir 1-144 arasi)

---

## GUN 2

```python
# backend/app/auth.py — require_role fonksiyonu
def require_role(allowed_roles: list[str]):
    """
    Kullanıcının belirtilen rollerden birine sahip olup olmadığını kontrol eden FastAPI Dependency'si.
    Kullanım: current_user = Depends(require_role(["saha_personeli", "yonetici"]))
    """

    async def role_checker(current_user: models.Kullanici = Depends(get_current_user)) -> models.Kullanici:
        if current_user.rol not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Bu işlemi yapmak için yetkiniz bulunmamaktadır."
            )
        return current_user

    return role_checker


# backend/app/main.py — require_role kullanan endpoint: sim_tetikle
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
```

Kaynak: `backend/app/auth.py` (satir 88-101 arasi) + `backend/app/main.py` (satir 966-987 arasi)

---

## GUN 3

```python
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
```

Kaynak: `backend/app/models.py` (satir 30-53 arasi)

---

## GUN 4

```javascript
const POLLING_INTERVAL_MS = 3000;   // 3 saniyede bir kontrol
const POLLING_MAX_DENEME = 60;     // Maksimum 60 deneme (~3 dakika), sonra HATA kabul

// ...

  const pollEt = useCallback(async () => {
    denemeRef.current += 1;

    if (denemeRef.current > POLLING_MAX_DENEME) {
      clearInterval(pollingRef.current);
      setPollingHata(true);
      return;
    }

    try {
      const veri = await getOlcum(olcumId);
      setOlcum(veri);

      if (veri.analiz_durumu === "TAMAMLANDI" || veri.analiz_durumu === "HATA") {
        clearInterval(pollingRef.current);
        setAnalizDurumu(veri.analiz_durumu);
        fadeIn();
        if (veri.risk_seviyesi === "KRİTİK") baslaPulse();
      }
    } catch (err) {
      console.warn("[Poll] İstek hatası:", err.message);
      // Bağlantı hatalarında polling'i durdurmuyoruz — retry mantığı var
    }
  }, [olcumId, fadeIn, baslaPulse]);

  useEffect(() => {
    // İlk yükleme — hemen bir kez çek
    pollEt();
    // Sonra her 3 saniyede bir
    pollingRef.current = setInterval(pollEt, POLLING_INTERVAL_MS);

    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, []);
```

Kaynak: `mobile/su-ai-mobile/src/screens/ResultScreen.js` (satir 37-38, 239-273 arasi)

---

## GUN 6

```python
async def hesapla_anomali_durumu(
    db: AsyncSession, olcum_verileri: dict, organization_id: uuid.UUID | None = None
):
    """
    Saha ölçüm verilerini alır, ilgili organizasyonun veritabanındaki dinamik
    anomali kuralları ve eşik değerleriyle karşılaştırarak en yüksek risk seviyesini ve tespitleri döndürür.
    """
    # 1. Organizasyon ID'yi belirle (argümandan, olcum_verileri["organization_id"]'den veya istasyon_id'den)
    if organization_id is None:
        org_val = olcum_verileri.get("organization_id")
        if org_val:
            organization_id = org_val
        elif olcum_verileri.get("istasyon_id"):
            st_res = await db.execute(
                select(models.Istasyon.organization_id).filter(
                    models.Istasyon.id == olcum_verileri["istasyon_id"]
                )
            )
            organization_id = st_res.scalar_one_or_none()

    # 2. İlgili organizasyona ait kuralları ve eşik değerlerini çek
    kurallar_stmt = select(models.AnomaliKurali)
    esikler_stmt = select(models.EsikDegeri)
    if organization_id is not None:
        kurallar_stmt = kurallar_stmt.filter(models.AnomaliKurali.organization_id == organization_id)
        esikler_stmt = esikler_stmt.filter(models.EsikDegeri.organization_id == organization_id)

    kurallar_result = await db.execute(kurallar_stmt)
    kurallar = kurallar_result.scalars().all()

    esikler_result = await db.execute(esikler_stmt)
    esikler = esikler_result.scalars().all()
```

Kaynak: `backend/app/engine.py` (satir 9-40 arasi)

---

## GUN 7

```python
    # 2. Adım: Kombinasyonel Anomali Kuralları (eval() güvenli ortam mantığı)
    # Örn: "serbest_klor < 0.2 and bulaniklik > 1.0"
    context = {
        "ph": olcum_verileri.get("ph"),
        "serbest_klor": olcum_verileri.get("serbest_klor"),
        "bulaniklik": olcum_verileri.get("bulaniklik"),
        "iletkenlik": olcum_verileri.get("iletkenlik"),
        "sicaklik": olcum_verileri.get("sicaklik"),
    }

    # None değerleri eval hatası vermemesi için filtrele
    clean_context = {k: v for k, v in context.items() if v is not None}
    print(f"DEBUG clean_context: {clean_context}")

    for kural in kurallar:
        print(f"DEBUG kural: {kural.kural_adi} | mantik: {kural.kural_mantigi}")
        try:
            # Kural mantığını güvenli bir şekilde çalıştır
            sonuc = eval(kural.kural_mantigi, {"__builtins__": {}}, clean_context)
            print(f"DEBUG eval sonucu: {sonuc}")
            if sonuc:
                tespit_edilen_anomaliler.append(
                    {"kural": kural.kural_adi, "mesaj": kural.saha_uyarisi, "risk": kural.risk_seviyesi}
                )
        except Exception as e:
            print(f"DEBUG HATA ({kural.kural_adi}): {e}")
```

Kaynak: `backend/app/engine.py` (satir 143-168 arasi)

---

## GUN 8

```python
@pytest.mark.asyncio
async def test_hesapla_anomali_durumu_iletkenlik(test_db):
    sonuc1 = await hesapla_anomali_durumu(test_db, {"iletkenlik": 200})
    assert sonuc1["en_yuksek_risk_seviyesi"] == "ORTA"
    
    sonuc2 = await hesapla_anomali_durumu(test_db, {"iletkenlik": 600})
    assert sonuc2["en_yuksek_risk_seviyesi"] == "ORTA"
    
    sonuc3 = await hesapla_anomali_durumu(test_db, {"iletkenlik": 2100})
    assert sonuc3["en_yuksek_risk_seviyesi"] == "KRİTİK"
```

Kaynak: `backend/tests/test_engine.py` (satir 99-108 arasi)

---

## GUN 9

```python
def olcum_tetikle(base_url: str, token: str, istasyon_id: int, mod: str) -> dict:
    """POST /api/sim/tetikle çağrısı yapar."""
    url = f"{base_url}/api/sim/tetikle?istasyon_id={istasyon_id}&mod={mod}"
    req = urllib.request.Request(
        url,
        data=b"",  # POST body boş — query params kullanıyoruz
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as yanit:
        return json.loads(yanit.read())
```

Kaynak: `backend/simulator.py` (satir 86-100 arasi)

---

## GUN 10

```python
from prometheus_client import Counter, Histogram

# --- Custom Business Metrics ---

anomaly_counter = Counter(
    "su_ai_anomaly_counter",
    "Anomalies detected, labelled by severity",
    ["severity"],  # kritik, uyari, normal, vb.
)

llm_call_counter = Counter(
    "su_ai_llm_call_counter",
    "LLM calls, labelled by provider and result",
    ["provider", "result"],  # provider: openai/ollama, result: success/error
)

llm_latency_histogram = Histogram(
    "su_ai_llm_latency_seconds",
    "LLM response time in seconds, labelled by provider",
    ["provider"],
    buckets=[0.5, 1.0, 2.5, 5.0, 10.0, 20.0, 30.0, 60.0],
)

judge_score_histogram = Histogram(
    "su_ai_judge_score_distribution",
    "LLM-as-Judge scores (0-100), labelled by prompt_version",
    ["prompt_version"],
    buckets=[0, 20, 40, 60, 80, 90, 100],
)

mqtt_message_counter = Counter(
    "su_ai_mqtt_message_counter",
    "MQTT messages received, labelled by status",
    ["status"],  # valid, malformed
)

trend_risk_histogram = Histogram(
    "su_ai_trend_risk_score",
    "Predictive trend risk scores (0-100), labelled by parameter",
    ["parameter"],
    buckets=[0, 20, 40, 60, 80, 100],
)
```

Kaynak: `backend/app/metrics.py` (satir 1-43 arasi — tum dosya)

> **Not:** `su_ai_anomaly_counter` tanimi `metrics.py` dosyasindadir. `main.py`'de `from app.metrics import anomaly_counter, trend_risk_histogram` satirlariyla ice aktarilmaktadir.

---

## GUN 11

```python
async def _get_llm_response(messages: list, fallback_to_local: bool = True, **kwargs) -> tuple[str, str]:
    """Hybrid LLM Çağrısı: Önce bulutu dener, hata alırsa yerele (Edge) düşer. Tuple(icerik, provider) doner."""
    has_cloud_key = os.getenv("OPENAI_API_KEY") is not None

    if has_cloud_key:
        try:
            # Bulut Denemesi
            start_time = time.time()
            if "temperature" not in kwargs:
                kwargs["temperature"] = 0.2
            response = await cloud_client.chat.completions.create(
                model="gpt-4o-mini", messages=messages, max_tokens=500, **kwargs
            )
            latency = time.time() - start_time
            llm_latency_histogram.labels(provider="openai").observe(latency)
            llm_call_counter.labels(provider="openai", result="success").inc()
            return response.choices[0].message.content, "openai"
        except Exception as e:
            llm_call_counter.labels(provider="openai", result="error").inc()
            logger.warning(
                f"[HYBRID-AI] Bulut (OpenAI) başarısız oldu ({e}). Yerel Edge (Ollama) sistemine geçiliyor..."
            )
```

Kaynak: `backend/app/llm_service.py` (satir 42-63 arasi)

---

## GUN 12

```python
    # Yerel Edge (Ollama) Fallback
    try:
        start_time = time.time()
        if "temperature" not in kwargs:
            kwargs["temperature"] = 0.2
        response = await local_client.chat.completions.create(
            model="llama3.2:1b", messages=messages, max_tokens=500, **kwargs
        )
        latency = time.time() - start_time
        llm_latency_histogram.labels(provider="ollama").observe(latency)
        llm_call_counter.labels(provider="ollama", result="success").inc()
        return response.choices[0].message.content, "ollama"
    except Exception as e:
        llm_call_counter.labels(provider="ollama", result="error").inc()
        logger.error(f"[HYBRID-AI] Yerel Edge (Ollama) de başarısız oldu: {e}")
        return "Sistem şu anda yanıt veremiyor. Lütfen IT departmanına haber verin.", "none"
```

Kaynak: `backend/app/llm_service.py` (satir 65-80 arasi)

---

## GUN 13

```python
MOCK_VERILER = [
    {
        "id": "vaka_1",
        "document": "Eyyübiye istasyonunda bulanıklık 1.5 NTU çıktığında, ana vanadaki filtre temizlenerek sorun çözüldü.",
    },
    {
        "id": "vaka_2",
        "document": "Karaköprü 2 nolu depoda serbest klor seviyesi 0.1 mg/L'ye düştüğünde klorlama dozaj pompası debisi artırılarak 0.3 mg/L seviyesine çekildi.",
    },
    {
        "id": "vaka_3",
        "document": "Haliliye şebeke hattında pH 9.8 ölçüldüğünde, bölgedeki yıkama vanası açılarak 2 saat hatta ters yıkama uygulandı ve pH 7.8'e normale döndü.",
    },
    {
        "id": "vaka_4",
        "document": "Birecik su deposunda iletkenlik 2600 µS/cm seviyesine ulaştığında kuyu karışım oranı değiştirilerek iletkenlik 1800 µS/cm seviyesine indirildi.",
    },
    {
        "id": "vaka_5",
        "document": "Siverek merkez istasyonunda sıcaklık 28°C ve klor 0.05 mg/L tespit edildiğinde, sıcaklığa bağlı klor uçuculuğu saptanmış ve ek şok klorlama yapılmıştır.",
    },
]
```

Kaynak: `backend/app/seed_rag.py` (satir 9-30 arasi)

---

## GUN 14

```text
Sen Şanlıurfa Su ve Kanalizasyon İdaresi (ŞUSKİ) bünyesinde çalışan kıdemli bir Altyapı ve Su Kalitesi Analiz Uzmanısın.

Görevin: Otomatik kural motorunun (engine.py) ürettiği anomali tespitlerini, saha personelinin anlayacağı teknik, kurumsal ve çözüm odaklı bir aksiyon planına dönüştürmek. Sen bir "narratör"sün — karar vermez, kural motorunun kararını profesyonel teknik dille detaylandırırsın.

ŞUSKİ Referans Eşikleri (Yalnızca mevcut verileri yorumlamak için kullan, yeni eşik üretme):
  - pH: 6.5 – 9.5
  - Serbest Klor: 0.2 – 0.5 mg/L | < 0.1 mg/L → Biyolojik Risk
  - Bulanıklık: < 5.0 NTU (Kritik: > 5.0 NTU) → Fiziksel Kirlilik
  - Basınç: 3.0 – 5.0 Bar | < 1.5 Bar → Altyapı Arızası / Boru Patlağı İhtimali

Risk Kategorileri (Ciddiyeti belirtirken kullan):
  - NORMAL: Şebeke güvenli, standartlar dahilinde.
  - DÜŞÜK: Yakın takip gerektiren durum.
  - ORTA: Önlem alınması gereken durum, saha ekibine bildir.
  - KRİTİK: ACİL müdahale — biyolojik risk, altyapı arızası veya bulanıklık artışı.

Anlatım Tarzı ve Kurallar:
- Teknik, çözüm odaklı ve kurumsal bir dil kullan. Gereksiz selamlama veya süslemeler yapma.
- KESİNLİKLE yeni yasal eşik, uydurma standart veya regülasyon üretme. Sadece verilen kural motoru ve hafıza verilerini kullan.
- Kurumsal Hafıza Kullanımı: Eğer Geçmiş Kurumsal Hafıza bloku verilmişse, "Geçmiş hafızaya atıfla:" gibi mekanik/robotik kalıplar KULLANMA. Bunun yerine geçmiş vakayı doğal ve somut bir tecrübe olarak aksiyon adımlarına entegre et (Örn: "Daha önce Haliliye/Karaköprü hattında benzer bir durumda [yapılan işlem] uygulanmıştı; sahada öncelikle [ilgili somut müdahale] yapılmalıdır.").
- Eğer 'PROAKTİF ÖNLEME' bloku verildiyse, aciliyet seviyesini tırmandırmadan önleyici adımları vurgula.

Çıktı Formatı (Sadece bu iki ana başlığı kullan):
**Mevcut Durum:**
- [Anomalinin teknik özeti ve ciddiyeti]

**Önerilen Aksiyon:**
- [1. Müdahale adımı]
- [2. Saha kontrol adımı]
- [Geçmiş saha tecrübesine dayalı somut yönlendirme — örn: 'Benzer bir vakada X bölgesinde Y yöntemiyle müdahale edilmişti, sahada benzer şekilde Z kontrol edilmelidir.']
```

Kaynak: `backend/app/prompts/narrator_v1.txt` (satir 1-31 arasi — tum dosya)

---

## GUN 15

```python
        # Determine trend direction using linear regression slope
        x = np.arange(len(data))
        y = np.array(data)
        slope, _ = np.polyfit(x, y, 1)

        trend_direction: Literal["rising", "falling", "stable"] = "stable"
        if slope > 0.05:
            trend_direction = "rising"
        elif slope < -0.05:
            trend_direction = "falling"

        # Calculate risk score (0-100) based on slope magnitude
        # Arbitrary multiplier to map typical slopes (0.05 - 0.3) to 0-100 score
        trend_risk_score = 0
        if trend_direction != "stable":
            risk = min(int(abs(slope) * 300), 100)
            trend_risk_score = risk
```

Kaynak: `backend/app/predictive_engine.py` (satir 92-108 arasi)

---

## GUN 16

```python
_PARAM_BOUNDS: dict[str, tuple[float | None, float | None]] = {
    "bulaniklik":   (0.0,  None),   # NTU: negatif olamaz
    "serbest_klor": (0.0,  None),   # mg/L: negatif olamaz
    "iletkenlik":   (0.0,  None),   # µS/cm: negatif olamaz
    "sicaklik":     (None, None),   # °C: donma altı fiziksel olarak geçerli
    "ph":           (0.0,  14.0),   # pH ölçeği: 0–14
}


def _apply_physical_bounds(
    parameter: str,
    value: float,
    station_id: int,
) -> tuple[float, bool]:
    """
    Clips *value* to the physical bounds defined for *parameter*.
    Returns (clipped_value, was_clipped).
    """
    bounds = _PARAM_BOUNDS.get(parameter.lower())
    if bounds is None:
        return value, False

    lo, hi = bounds
    original = value
    if lo is not None and value < lo:
        value = lo
    if hi is not None and value > hi:
        value = hi

    clipped = value != original
    if clipped:
        logger.debug(
            "analyze_trend: projected_value clipped %.4f → %.4f "
            "(param=%s, station=%d)",
            original, value, parameter, station_id,
        )
    return value, clipped

# ... (analyze_trend fonksiyonu icinde Holt cagrisi)

        # Predict next value using Holt's Linear Trend method
        series = pd.Series(data)
        model = Holt(series, initialization_method="estimated")
        fit_model = model.fit()
        forecast = fit_model.forecast(1)
        projected_value = float(forecast.iloc[0])
```

Kaynak: `backend/app/predictive_engine.py` (satir 16-52, 85-90 arasi)

---

## GUN 17

```python
# DÜZELTME: RAG bağlamından (su_kriz_hafizasi) habersizlik nedeniyle narratörün meşru kurumsal
# geçmiş vaka atıflarının (örn. ilçe/bölge referansları) halüsinasyon sayılarak puan kırılmasını (85 puan tavanı)
# önlemek amacıyla benzer_vakalar parametresi eklendi ve yargıç promptuna dahil edildi.
async def degerlendir_llm_ciktisi(
    olcum_id: int,
    anomali_raporu: dict,
    llm_onerisi: str,
    db_factory,
    provider: str,
    istasyon_id: int,
    benzer_vakalar: list[str] | None = None,
):
    """
    LLM'in ürettiği çıktıyı arka planda denetler (LLM-as-a-Judge) ve veritabanına yazar.
    FastAPI BackgroundTasks için tasarlanmıştır.
    """
    # Anomali listesini okunabilir formata çevir
    anomali_ozeti = (
        "\n".join([f"  - [{a['risk']}] {a['kural']}: {a['mesaj']}" for a in anomali_raporu.get("detaylar", [])])
        or "  - Anomali tespit edilmedi (NORMAL durum)."
    )

    vaka_baglami = ""
    if benzer_vakalar:
        vaka_baglami = (
            "\n=== DOĞRULANMIŞ KURUMSAL HAFIZA (RAG Vaka Kayıtları) ===\n"
            "Aşağıdaki geçmiş vakalar sisteme RAG hafızasından sağlanmıştır. LLM'in bu vakalara/ilçelere yaptığı atıflar meşrudur, halüsinasyon sayılmamalıdır:\n"
            + "\n".join([f"  - {v}" for v in benzer_vakalar])
            + "\n"
        )

    kullanici_promptu = f"""Şu bilgileri değerlendirmeni istiyorum:

=== ANOMALİ RAPORU (Gerçek, değişmez referans) ===
Genel Durum: {anomali_raporu.get('durum', 'BILINMEYEN')}
En Yüksek Risk: {anomali_raporu.get('en_yuksek_risk_seviyesi', 'NORMAL')}
Tespit Edilen Anomaliler:
{anomali_ozeti}
{vaka_baglami}
=== LLM ÖNERİSİ (Denetlenecek metin) ===
{llm_onerisi}

Yukarıdaki öneriyi anomali raporu ve doğrulanmış kurumsal hafıza ile kıyasla. Kurumsal hafızadaki geçmiş vakalara yapılan atıfları halüsinasyon sayma. Gerçek halüsinasyonları veya eksikleri tespit et ve uygunluk puanını JSON formatında dön."""

    try:
        messages = [
            {"role": "system", "content": _get_judge_prompt()},
            {"role": "user", "content": kullanici_promptu},
        ]

        yanit_str, _ = await _get_llm_response(messages, response_format={"type": "json_object"}, temperature=0.1)

        sonuc_json = json.loads(yanit_str)
        uygunluk_puani = int(sonuc_json.get("uygunluk_puani", 0))
        degerlendirme_notu = str(sonuc_json.get("degerlendirme_notu", "Parse hatası."))
        uygunluk_puani = max(0, min(100, uygunluk_puani))

        # Record metric
        judge_score_histogram.labels(prompt_version="v1").observe(uygunluk_puani)

    except Exception as e:
        logger.error(f"[Judge] Hata oluştu: {e}")
        uygunluk_puani = 0
        degerlendirme_notu = f"Yargıç LLM hatası: {str(e)[:200]}"
```

Kaynak: `backend/app/judge_service.py` (satir 24-87 arasi)

---

## GUN 18

```python
# backend/app/judge_service.py — RAG baglaminin prompta eklendigi kisim
    vaka_baglami = ""
    if benzer_vakalar:
        vaka_baglami = (
            "\n=== DOĞRULANMIŞ KURUMSAL HAFIZA (RAG Vaka Kayıtları) ===\n"
            "Aşağıdaki geçmiş vakalar sisteme RAG hafızasından sağlanmıştır. LLM'in bu vakalara/ilçelere yaptığı atıflar meşrudur, halüsinasyon sayılmamalıdır:\n"
            + "\n".join([f"  - {v}" for v in benzer_vakalar])
            + "\n"
        )

    kullanici_promptu = f"""Şu bilgileri değerlendirmeni istiyorum:

=== ANOMALİ RAPORU (Gerçek, değişmez referans) ===
Genel Durum: {anomali_raporu.get('durum', 'BILINMEYEN')}
En Yüksek Risk: {anomali_raporu.get('en_yuksek_risk_seviyesi', 'NORMAL')}
Tespit Edilen Anomaliler:
{anomali_ozeti}
{vaka_baglami}
=== LLM ÖNERİSİ (Denetlenecek metin) ===
{llm_onerisi}

Yukarıdaki öneriyi anomali raporu ve doğrulanmış kurumsal hafıza ile kıyasla. Kurumsal hafızadaki geçmiş vakalara yapılan atıfları halüsinasyon sayma. Gerçek halüsinasyonları veya eksikleri tespit et ve uygunluk puanını JSON formatında dön."""
```

```text
# backend/app/prompts/judge_v1.txt — tum dosya
Sen Sistem Çıktısı Kalite Kontrol Denetçisisin.
Görev: Verilen "Anomali Raporu" ve "Doğrulanmış Kurumsal Hafıza (RAG)" bağlamı ile üretilen "LLM Önerisi"ni karşılaştır.
ÖNEMLİ KURAL: "Doğrulanmış Kurumsal Hafıza" bölümündeki geçmiş vaka ve ilçe/bölge kayıtları sisteme ait meşru referanslardır. Narratörün bu geçmiş vakalara (örneğin ilçe adı, geçmiş tecrübe, benzer arıza çözümü) yaptığı atıflar KESİNLİKLE halüsinasyon DEĞİLDİR ve puan kırılmamalıdır.
Öneri, regülasyon kurallarına uygun mu? Gerçek dışı eşik veya raporda/RAG hafızasında olmayan uydurma yasal referans var mı? Mantıklı ve eksiksiz mi?
Çıktı Formatı:
Sadece saf JSON dön:
{"uygunluk_puani": <0-100 arasi sayi>, "degerlendirme_notu": "<aciklama>"}
Başka hiçbir ek metin yazma.

```

Kaynak: `backend/app/judge_service.py` (satir 46-66 arasi) + `backend/app/prompts/judge_v1.txt` (satir 1-10 arasi)

---

## GUN 19

```python
def on_message(client, userdata, msg):
    try:
        raw_data = json.loads(msg.payload.decode("utf-8"))
        payload = MqttPayload(**raw_data)
        logger.info(f"[MQTT] Received valid payload for station {payload.station_id}")
        mqtt_message_counter.labels(status="valid").inc()

        # Bridge to async FastAPI world
        if main_loop and main_loop.is_running():
            asyncio.run_coroutine_threadsafe(process_mqtt_payload(payload), main_loop)
        else:
            logger.error("[MQTT] Event loop is not running")

    except json.JSONDecodeError:
        mqtt_message_counter.labels(status="malformed").inc()
        logger.error(f"[MQTT] Malformed JSON received on {msg.topic}: {msg.payload}")
    except ValidationError as e:
        mqtt_message_counter.labels(status="malformed").inc()
        logger.error(f"[MQTT] Validation error for payload on {msg.topic}: {e.errors()}")
    except Exception as e:
        mqtt_message_counter.labels(status="malformed").inc()
        logger.error(f"[MQTT] Unexpected error processing message on {msg.topic}: {e}")
```

Kaynak: `backend/app/mqtt_client.py` (satir 84-105 arasi)

---

## GUN 20

```python
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
```

Kaynak: `backend/app/main.py` (satir 614-627 arasi)

---

## GUN 21

```javascript
/**
 * Yeni bir offline ölçüm kaydeder.
 * @returns {number} Oluşturulan kaydın yerel ID'si
 */
export async function kaydetOlcum(olcumData) {
  return await withDB(async (db) => {
    const result = await db.runAsync(
      `INSERT INTO bekleyen_olcumler
         (istasyon_id, ph, serbest_klor, bulaniklik, iletkenlik, sicaklik, personel_notu)
       VALUES (?, ?, ?, ?, ?, ?, ?)`,
      [
        olcumData.istasyon_id,
        olcumData.ph ?? null,
        olcumData.serbest_klor ?? null,
        olcumData.bulaniklik ?? null,
        olcumData.iletkenlik ?? null,
        olcumData.sicaklik ?? null,
        olcumData.personel_notu ?? null,
      ]
    );
    return result.lastInsertRowId;
  });
}
```

Kaynak: `mobile/su-ai-mobile/src/services/offlineStorage.js` (satir 51-73 arasi)

---

## GUN 22

```json
    {
      "title": "LLM Latency Percentiles (p50 & p95)",
      "type": "timeseries",
      "gridPos": {"x": 0, "y": 24, "w": 12, "h": 8},
      "targets": [
        {"expr": "histogram_quantile(0.95, sum(rate(su_ai_llm_latency_seconds_bucket[5m])) by (le, provider))", "legendFormat": "{{provider}} - p95 Latency (s)"},
        {"expr": "histogram_quantile(0.50, sum(rate(su_ai_llm_latency_seconds_bucket[5m])) by (le, provider))", "legendFormat": "{{provider}} - p50 (Median) (s)"}
      ]
    },
```

Kaynak: `grafana/dashboards/su-ai-overview.json` (satir 57-65 arasi — LLM Latency Percentiles paneli)

---

## GUN 23

```python
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
```

Kaynak: `backend/app/main.py` (satir 402-421 arasi)

---

## GUN 24

```yaml
  postgres:
    image: postgres:15
    container_name: su-ai-postgres
    command: postgres -c max_connections=250
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-postgres}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-postgres}
      POSTGRES_DB: ${POSTGRES_DB:-su_ai}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - su-ai-network
    ports:
      - "5432:5432"
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-postgres} -d ${POSTGRES_DB:-su_ai}"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s

  # --- backend depends_on ve healthcheck ---
    depends_on:
      postgres:
        condition: service_healthy
      chromadb:
        condition: service_started
      ollama:
        condition: service_started
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/docs')"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 20s
```

Kaynak: `docker-compose.yml` (satir 16-36 ve 86-98 arasi)

---

## GUN 25

```python
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
```

Kaynak: `backend/tests/test_isolation_demo.py` (satir 1-35 arasi — tum dosya)

---

## GUN 26

```python
import ast


def kural_mantigi_gecerli_mi(kural_mantigi: str) -> tuple[bool, str | None]:
    """
    Bir kural_mantigi string'inin geçerli Python syntax'ına sahip olup
    olmadığını kontrol eder. (True, None) veya (False, hata_mesaji) döner.
    """
    if not isinstance(kural_mantigi, str) or not kural_mantigi.strip():
        return False, "Kural mantığı boş olamaz."
    try:
        ast.parse(kural_mantigi, mode="eval")
        return True, None
    except SyntaxError as e:
        return False, str(e)
```

Kaynak: `backend/app/validators.py` (satir 1-16 arasi — tum dosya)

---

## GUN 27

```python
def upgrade() -> None:
    """Upgrade schema - Add multi-tenancy organization_id to esik_degerleri and anomali_kurallari."""
    # 1. Add organization_id column as NULLABLE first
    op.add_column('esik_degerleri', sa.Column('organization_id', sa.Uuid(), nullable=True))
    op.add_column('anomali_kurallari', sa.Column('organization_id', sa.Uuid(), nullable=True))

    # 2. Backfill existing records with the existing default organization ID
    default_org_id = uuid.uuid4()
    op.execute(f"""
        DO $$
        DECLARE
            default_org uuid;
        BEGIN
            SELECT id INTO default_org FROM organizations ORDER BY created_at ASC LIMIT 1;
            IF default_org IS NULL THEN
                INSERT INTO organizations (id, name, created_at) VALUES ('{default_org_id}', 'Default Organization', NOW()) RETURNING id INTO default_org;
            END IF;
            UPDATE esik_degerleri SET organization_id = default_org WHERE organization_id IS NULL;
            UPDATE anomali_kurallari SET organization_id = default_org WHERE organization_id IS NULL;
        END $$;
    """)

    # 3. Alter columns to be NOT NULL
    op.alter_column('esik_degerleri', 'organization_id', nullable=False)
    op.alter_column('anomali_kurallari', 'organization_id', nullable=False)

    # 4. Create Foreign Keys
    op.create_foreign_key('fk_esik_degerleri_org', 'esik_degerleri', 'organizations', ['organization_id'], ['id'])
    op.create_foreign_key('fk_anomali_kurallari_org', 'anomali_kurallari', 'organizations', ['organization_id'], ['id'])

    # 5. Replace global unique constraint on parametre_adi with per-organization unique constraint
    op.execute("ALTER TABLE esik_degerleri DROP CONSTRAINT IF EXISTS esik_degerleri_parametre_adi_key;")
    op.create_unique_constraint('uq_esik_org_param', 'esik_degerleri', ['organization_id', 'parametre_adi'])
```

Kaynak: `backend/alembic/versions/e5a8d7901234_multi_tenancy_esikler_kurallar.py` (satir 22-54 arasi)

---

## GUN 28

```javascript
// services/api.js
// Su-AI Backend API Katmanı
import Constants from 'expo-constants';

// Backend API URL'si merkezi olarak app.json -> expo.extra.apiBaseUrl üzerinden okunur.
// Yerel ağ IP'si değiştiğinde sadece app.json içindeki apiBaseUrl değerini güncellemek yeterlidir.
export const API_URL =
  Constants?.expoConfig?.extra?.apiBaseUrl ||
  Constants?.manifest?.extra?.apiBaseUrl ||
  "http://192.168.1.104:8080";

const BASE_URL = API_URL;
```

Kaynak: `mobile/su-ai-mobile/src/services/api.js` (satir 1-12 arasi)

---

## Ozet

| Gun  | Durum      | Dosya |
|------|-----------|-------|
| GUN 1  | Bulundu | `docker-compose.yml` |
| GUN 2  | Bulundu | `backend/app/auth.py` + `backend/app/main.py` |
| GUN 3  | Bulundu | `backend/app/models.py` |
| GUN 4  | Bulundu | `mobile/su-ai-mobile/src/screens/ResultScreen.js` |
| GUN 6  | Bulundu | `backend/app/engine.py` |
| GUN 7  | Bulundu | `backend/app/engine.py` |
| GUN 8  | Bulundu | `backend/tests/test_engine.py` |
| GUN 9  | Bulundu | `backend/simulator.py` |
| GUN 10 | Bulundu | `backend/app/metrics.py` |
| GUN 11 | Bulundu | `backend/app/llm_service.py` |
| GUN 12 | Bulundu | `backend/app/llm_service.py` |
| GUN 13 | Bulundu | `backend/app/seed_rag.py` |
| GUN 14 | Bulundu | `backend/app/prompts/narrator_v1.txt` |
| GUN 15 | Bulundu | `backend/app/predictive_engine.py` |
| GUN 16 | Bulundu | `backend/app/predictive_engine.py` |
| GUN 17 | Bulundu | `backend/app/judge_service.py` |
| GUN 18 | Bulundu | `backend/app/judge_service.py` + `backend/app/prompts/judge_v1.txt` |
| GUN 19 | Bulundu | `backend/app/mqtt_client.py` |
| GUN 20 | Bulundu | `backend/app/main.py` |
| GUN 21 | Bulundu | `mobile/su-ai-mobile/src/services/offlineStorage.js` |
| GUN 22 | Bulundu | `grafana/dashboards/su-ai-overview.json` |
| GUN 23 | Bulundu | `backend/app/main.py` |
| GUN 24 | Bulundu | `docker-compose.yml` |
| GUN 25 | Bulundu | `backend/tests/test_isolation_demo.py` |
| GUN 26 | Bulundu | `backend/app/validators.py` |
| GUN 27 | Bulundu | `backend/alembic/versions/e5a8d7901234_multi_tenancy_esikler_kurallar.py` |
| GUN 28 | Bulundu | `mobile/su-ai-mobile/src/services/api.js` |

**Basariyla bulunan: 27 / 27**
**Bulunamayan: 0**

> Not: GUN 5 istek listesinde yer almadigi icin atland(GUN 4ten sonra dogrudan GUN 6 verildi).
> GUN 10 icin Prometheus Counter tanimlari main.py degil backend/app/metrics.py dosyasinda tutulmaktadir.
> GUN 2 icin require_role fonksiyonu backend/app/auth.py de, onu kullanan sim_tetikle endpointi ise backend/app/main.py dedir.
