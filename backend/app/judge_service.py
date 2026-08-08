import json
import logging

from sqlalchemy.future import select

from app import models
from app.llm_service import _get_llm_response

logger = logging.getLogger(__name__)

YARGIC_SISTEM_PROMPTU = """Sen Sistem Çıktısı Kalite Kontrol Denetçisisin.
Görev: Verilen "Anomali Raporu" ile üretilen "LLM Önerisi"ni karşılaştır. Öneri, regülasyon kurallarına uygun mu? Halüsinasyon (uydurma referans veya yasal olmayan eşik) var mı? Mantıklı ve eksiksiz mi?
Çıktı Formatı:
Sadece saf JSON dön:
{"uygunluk_puani": <0-100 arasi sayi>, "degerlendirme_notu": "<aciklama>"}
Başka hiçbir ek metin yazma.
"""


async def degerlendir_llm_ciktisi(olcum_id: int, anomali_raporu: dict, llm_onerisi: str, db_factory):
    """
    LLM'in ürettiği çıktıyı arka planda denetler (LLM-as-a-Judge) ve veritabanına yazar.
    FastAPI BackgroundTasks için tasarlanmıştır.
    """
    # Anomali listesini okunabilir formata çevir
    anomali_ozeti = (
        "\n".join([f"  - [{a['risk']}] {a['kural']}: {a['mesaj']}" for a in anomali_raporu.get("detaylar", [])])
        or "  - Anomali tespit edilmedi (NORMAL durum)."
    )

    kullanici_promptu = f"""Şu bilgileri değerlendirmeni istiyorum:

=== ANOMALİ RAPORU (Gerçek, değişmez referans) ===
Genel Durum: {anomali_raporu.get('durum', 'BILINMEYEN')}
En Yüksek Risk: {anomali_raporu.get('en_yuksek_risk_seviyesi', 'NORMAL')}
Tespit Edilen Anomaliler:
{anomali_ozeti}

=== LLM ÖNERİSİ (Denetlenecek metin) ===
{llm_onerisi}

Yukarıdaki öneriyi anomali raporuyla kıyasla, halüsinasyonları veya eksikleri tespit et ve uygunluk puanını JSON formatında dön."""

    try:
        messages = [
            {"role": "system", "content": YARGIC_SISTEM_PROMPTU},
            {"role": "user", "content": kullanici_promptu},
        ]

        yanit_str = await _get_llm_response(messages, response_format={"type": "json_object"}, temperature=0.1)

        sonuc_json = json.loads(yanit_str)
        uygunluk_puani = int(sonuc_json.get("uygunluk_puani", 0))
        degerlendirme_notu = str(sonuc_json.get("degerlendirme_notu", "Parse hatası."))
        uygunluk_puani = max(0, min(100, uygunluk_puani))

    except Exception as e:
        logger.error(f"[Judge] Hata oluştu: {e}")
        uygunluk_puani = 0
        degerlendirme_notu = f"Yargıç LLM hatası: {str(e)[:200]}"

    logger.info(f"[Judge] olcum_id={olcum_id} | puan={uygunluk_puani} | not={degerlendirme_notu}")

    # Sonucu veritabanına kaydet
    async with db_factory() as db:
        try:
            result = await db.execute(
                select(models.AnalizMetrikleri).filter(models.AnalizMetrikleri.olcum_id == olcum_id)
            )
            mevcut_metrik = result.scalars().first()

            if mevcut_metrik:
                mevcut_metrik.llm_onerisi = llm_onerisi
                mevcut_metrik.uygunluk_puani = uygunluk_puani
                mevcut_metrik.degerlendirme_notu = degerlendirme_notu
            else:
                yeni_metrik = models.AnalizMetrikleri(
                    olcum_id=olcum_id,
                    llm_onerisi=llm_onerisi,
                    uygunluk_puani=uygunluk_puani,
                    degerlendirme_notu=degerlendirme_notu,
                )
                db.add(yeni_metrik)

            await db.commit()
        except Exception as db_err:
            logger.error(f"[Judge] Veritabanı kayıt hatası (olcum_id={olcum_id}): {db_err}")
