# app/llm_service.py
"""
Su-AI LLM Servisi — Narratör Rolü
===================================
MİMARİ KISIT: Bu servis KESİNLİKLE eşik değeri kontrolü yapmaz ve
anomali tespit etmez. Tek görevi, engine.py'dan gelen kural motoru
sonucunu saha personelinin anlayacağı teknik bir aksiyon planına
çevirmektir. LLM bir "narratör"dür, karar veren değil.
"""

import logging
import os
import time

from dotenv import load_dotenv
from openai import AsyncOpenAI

from app.metrics import llm_call_counter, llm_latency_histogram

load_dotenv()

logger = logging.getLogger(__name__)

# Hybrid Edge-Cloud Mimarisi:
# 1. Bulut (OpenAI) denenir.
# 2. İnternet yoksa, kota dolmuşsa veya API key yoksa Yerel Edge (Ollama) sistemine düşer (Fallback).

cloud_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", "dummy"), timeout=15.0)
local_client = AsyncOpenAI(base_url="http://ollama:11434/v1", api_key="ollama", max_retries=0, timeout=90.0)


async def _get_llm_response(messages: list, fallback_to_local: bool = True, **kwargs) -> tuple[str, str]:
    """Hybrid LLM Çağrısı: Önce bulutu dener, hata alırsa yerele (Edge) düşer. Tuple(icerik, provider) doner."""
    has_cloud_key = os.getenv("OPENAI_API_KEY") is not None

    if has_cloud_key:
        try:
            # Bulut Denemesi
            start_time = time.time()
            response = await cloud_client.chat.completions.create(
                model="gpt-4o-mini", messages=messages, temperature=0.2, max_tokens=500, **kwargs
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

    # Yerel Edge (Ollama) Fallback
    try:
        start_time = time.time()
        response = await local_client.chat.completions.create(
            model="llama3.2:1b", messages=messages, temperature=0.2, max_tokens=500, **kwargs
        )
        latency = time.time() - start_time
        llm_latency_histogram.labels(provider="ollama").observe(latency)
        llm_call_counter.labels(provider="ollama", result="success").inc()
        return response.choices[0].message.content, "ollama"
    except Exception as e:
        llm_call_counter.labels(provider="ollama", result="error").inc()
        logger.error(f"[HYBRID-AI] Yerel Edge (Ollama) de başarısız oldu: {e}")
        return "Sistem şu anda yanıt veremiyor. Lütfen IT departmanına haber verin.", "none"


def _get_narrator_prompt() -> str:
    prompt_path = os.path.join(os.path.dirname(__file__), "prompts", "narrator_v1.txt")
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        logger.warning(f"Prompt dosyası bulunamadı: {prompt_path}. Varsayılan prompt kullanılıyor.")
        return "Sen Şanlıurfa Su ve Kanalizasyon İdaresi (ŞUSKİ) bünyesinde çalışan kıdemli bir Altyapı ve Su Kalitesi Analiz Uzmanısın."


async def olustur_teknik_aksiyon_onerisi(olcum_id: int, anomali_raporu: dict, db) -> tuple[str, str, str]:
    """
    Kural motoru sonucunu alarak saha personeline yönelik teknik aksiyon önerisi üretir.
    """
    from sqlalchemy.future import select

    from app import models

    # Fetch olcum_verisi from db
    result = await db.execute(select(models.SuOlcumu).filter(models.SuOlcumu.id == olcum_id))
    olcum = result.scalars().first()
    if not olcum:
        return "Ölçüm bulunamadı", "HATA", "none"

    olcum_verisi = {
        "ph": olcum.ph,
        "serbest_klor": olcum.serbest_klor,
        "bulaniklik": olcum.bulaniklik,
        "iletkenlik": olcum.iletkenlik,
        "sicaklik": olcum.sicaklik,
    }

    kural_motoru_sonucu = anomali_raporu

    # Risk seviyesine göre aciliyet bağlamı
    risk = kural_motoru_sonucu.get("en_yuksek_risk_seviyesi", "NORMAL")

    # NORMAL durumlar için LLM çağırmadan doğrudan standart yanıt dön.
    if risk == "NORMAL":
        oneri = "**Mevcut Durum:**\n- Şebeke suyu güvenli, tüm değerler standartlar dahilindedir. Herhangi bir anomali tespit edilmemiştir.\n\n**Önerilen Aksiyon:**\n- Rutin kontrol takvimine göre bir sonraki ölçümü planlayın.\n- Ekstra bir aksiyon gerekmemektedir."
        logger.info("LLM atlandı: Risk NORMAL. Varsayılan metin döndürüldü.")
        return oneri, "BASARILI", "static"

    aciliyet_map = {
        "DÜŞÜK": "yakın takip gerektiren durum",
        "ORTA": "önlem alınması gereken durum",
        "KRİTİK": "ACİL müdahale gerektiren kritik durum",
    }
    aciliyet = aciliyet_map.get(risk, "belirsiz durum")

    # Anomali detaylarını okunabilir formata çevir
    anomali_listesi = (
        "\n".join([f"  - [{a['risk']}] {a['kural']}: {a['mesaj']}" for a in kural_motoru_sonucu.get("detaylar", [])])
        or "  - Anomali tespit edilmedi."
    )

    # RAG Araması (Semantic Search)
    import asyncio

    from app.rag_service import search_rag_memory

    query_text = f"Anomaliler: {anomali_listesi} - Ölçüm: pH={olcum_verisi.get('ph')}, Klor={olcum_verisi.get('serbest_klor')}, Bulanıklık={olcum_verisi.get('bulaniklik')}"
    benzer_vakalar = await asyncio.to_thread(search_rag_memory, query_text, 2)

    vaka_metni = ""
    if benzer_vakalar:
        vaka_metni = "=== GEÇMİ KURUMSAL HAFIZA (Benzer Vakalar) ===\n" + "\n".join([f"- {v}" for v in benzer_vakalar])

    # Kullanıcı promptu — sadece mevcut veriyi içerir
    kullanici_promptu = f"""Aşağıdaki otomatik kural motoru analiz sonucunu teknik aksiyon önerisine çevir.

=== KURAL MOTORU ÇIKTISI (Bu veriden başka kaynak kullanma) ===
Genel Durum: {kural_motoru_sonucu.get('durum', 'BİLİNMEYEN')}
En Yüksek Risk Seviyesi: {risk} ({aciliyet})

Tespit Edilen Anomaliler:
{anomali_listesi}

=== ÖLÇÜM VERİLERİ ===
pH: {olcum_verisi.get('ph', 'Ölçülmedi')}
Serbest Klor: {olcum_verisi.get('serbest_klor', 'Ölçülmedi')} mg/L
Bulanıklık: {olcum_verisi.get('bulaniklik', 'Ölçülmedi')} NTU
İletkenlik: {olcum_verisi.get('iletkenlik', 'Ölçülmedi')} µS/cm
Sıcaklık: {olcum_verisi.get('sicaklik', 'Ölçülmedi')} °C

{vaka_metni}

=== TALİMAT ===
Yukarıdaki kural motoru çıktısına ve Geçmiş Kurumsal Hafıza'ya dayanarak saha personeli için somut, numaralı teknik aksiyon adımları oluştur.
UNUTMA: Yeni eşik/yasal referans üretme, sadece verilen veriyi yorumla ve geçmiş hafızaya atıf yap."""

    try:
        # LLM'e (Hybrid) İstek At
        messages = [
            {"role": "system", "content": _get_narrator_prompt()},
            {"role": "user", "content": kullanici_promptu},
        ]

        oneri, provider = await _get_llm_response(messages)
        logger.info(f"LLM aksiyon önerisi başarıyla oluşturuldu. Risk: {risk}")
        return oneri, "BASARILI", provider

    except Exception as e:
        logger.error(f"LLM servisi hatası: {e}")
        # Fallback: LLM olmadan da sistem çalışmaya devam eder
        fallback = _olustur_fallback_oneri(kural_motoru_sonucu)
        return fallback, "DEVRE_DISI", "fallback"


def _olustur_fallback_oneri(kural_motoru_sonucu: dict) -> str:
    """
    LLM servisine ulaşılamadığında kural motoru sonucundan
    basit bir metin oluşturur. İnternet yokken de sistem çalışır.
    """
    risk = kural_motoru_sonucu.get("en_yuksek_risk_seviyesi", "NORMAL")
    detaylar = kural_motoru_sonucu.get("detaylar", [])

    if not detaylar:
        return (
            "Ölçüm değerleri normal sınırlar içinde görünmektedir. "
            "Rutin kontrol takviminize göre bir sonraki ölçümü planlayın."
        )

    aksiyon_satirlari = [f"⚠ Risk Seviyesi: {risk}\n"]
    for i, anomali in enumerate(detaylar, 1):
        aksiyon_satirlari.append(f"{i}. {anomali['mesaj']}")

    aksiyon_satirlari.append(
        "\n[NOT: LLM servisi şu an erişilemiyor. "
        "Yukarıdaki tespitler kural motoru tarafından otomatik olarak üretilmiştir.]"
    )
    return "\n".join(aksiyon_satirlari)


# (Eski LLM-as-a-Judge kodu kaldirildi, yerine judge_service.py kullaniliyor)


# ---------------------------------------------------------------------------
# Arka Plan Görevi (FastAPI BackgroundTasks ile çağrılır)
# ---------------------------------------------------------------------------


async def arka_planda_analiz_et(olcum_id: int, db_factory) -> None:
    """
    FastAPI BackgroundTasks tarafından çağrılan asenkron arka plan görevi.

    Akış:
    1. Yeni bir DB oturumu aç (request oturumunu paylaşmaz — thread-safe)
    2. Ölçümü DB'den çek
    3. Kural motorunu çalıştır
    4. LLM narratörüne gönder → aksiyon_onerisi
    5. LLM-as-a-Judge denetimini çalıştır → AnalizMetrikleri kaydı oluştur
    6. analiz_durumu = "TAMAMLANDI"
    7. Hata durumunda analiz_durumu = "HATA"
    """
    from sqlalchemy.future import select

    from app import models
    from app.engine import hesapla_anomali_durumu

    async with db_factory() as db:
        try:
            # 1. Ölçümü DB'den çek
            result = await db.execute(select(models.SuOlcumu).filter(models.SuOlcumu.id == olcum_id))
            olcum = result.scalars().first()
            if not olcum:
                logger.error(f"[BG] Ölçüm bulunamadı: id={olcum_id}")
                return

            logger.info(f"[BG] Analiz başlatıldı: ölçüm id={olcum_id}")

            # 2. Kural motorunu çalıştır
            analiz_girdisi = {
                "ph": olcum.ph,
                "serbest_klor": olcum.serbest_klor,
                "bulaniklik": olcum.bulaniklik,
                "iletkenlik": olcum.iletkenlik,
                "sicaklik": olcum.sicaklik,
            }
            kural_motoru_sonucu = await hesapla_anomali_durumu(db, analiz_girdisi)

            # 3. LLM narratör → aksiyon önerisi
            teknik_oneri, llm_durumu, provider = await olustur_teknik_aksiyon_onerisi(
                olcum_id=olcum_id, anomali_raporu=kural_motoru_sonucu, db=db
            )

            # 4. Sonuçları DB'ye yaz — önce olcum alanları
            olcum.risk_seviyesi = kural_motoru_sonucu.get("en_yuksek_risk_seviyesi", "NORMAL")
            olcum.aksiyon_onerisi = teknik_oneri
            olcum.analiz_durumu = "TAMAMLANDI"
            await db.commit()

            logger.info(f"[BG] Tamamlandi: id={olcum_id} | " f"risk={olcum.risk_seviyesi} | llm={llm_durumu}")

            # 5. LLM-as-a-Judge → Bu DB commit edildikten sonra çalışsın (DB çakışması olmasın diye db_factory geçilir)
            import asyncio

            from app.judge_service import degerlendir_llm_ciktisi

            asyncio.create_task(
                degerlendir_llm_ciktisi(
                    olcum_id, kural_motoru_sonucu, teknik_oneri, db_factory, provider, olcum.istasyon_id
                )
            )

        except Exception as e:
            logger.error(f"[BG] Beklenmeyen hata (id={olcum_id}): {e}", exc_info=True)
            try:
                result = await db.execute(select(models.SuOlcumu).filter(models.SuOlcumu.id == olcum_id))
                olcum = result.scalars().first()
                if olcum:
                    olcum.analiz_durumu = "HATA"
                    await db.commit()
            except Exception as commit_err:
                logger.error(f"[BG] HATA durumu yazılamadı: {commit_err}")
