// services/syncService.js
// Su-AI Senkronizasyon Servisi
// Offline kayıtlı ölçümleri internete bağlanıldığında toplu olarak backend'e gönderir.

import { topluOlcumGonder } from "./api";
import {
  getBekleyenOlcumler,
  guncelleDurum,
  temizleTamamlananlar,
} from "./offlineStorage";
import {
  kritikAnomalibildirimi,
  senkronizasyonTamamlandiBildirimi,
} from "./notificationService";

let _syncCalisiyorMu = false; // Eş zamanlı sync önleme kilidi

/**
 * Bekleyen offline ölçümleri backend'e senkronize eder.
 *
 * Akış:
 * 1. SQLite'tan 'bekliyor' durumundaki tüm ölçümleri çek
 * 2. Durum → 'gonderiliyor' olarak işaretle
 * 3. Toplu API isteği gönder
 * 4. Başarılıları → 'tamamlandi', hatalıları → 'hata' yap
 * 5. KRİTİK dönenler için yerel bildirim tetikle
 * 6. Eski tamamlananları temizle
 *
 * @returns {{ basarili: number, basarisiz: number, kritik: number }}
 */
export async function senkronizeEt() {
  if (_syncCalisiyorMu) {
    console.log("[Sync] Zaten bir sync işlemi çalışıyor, atlanıyor.");
    return null;
  }

  _syncCalisiyorMu = true;
  console.log("[Sync] Senkronizasyon başlatıldı...");

  try {
    const bekleyenler = await getBekleyenOlcumler();

    if (bekleyenler.length === 0) {
      console.log("[Sync] Bekleyen ölçüm yok.");
      return { basarili: 0, basarisiz: 0, kritik: 0 };
    }

    console.log(`[Sync] ${bekleyenler.length} bekleyen ölçüm bulundu.`);

    // Hepsini 'gonderiliyor' olarak işaretle
    for (const olcum of bekleyenler) {
      await guncelleDurum(olcum.id, "gonderiliyor");
    }

    // API'ye uygun formata dönüştür (_yerel_id ekle — takip için)
    const apiGonderimi = bekleyenler.map((o) => ({
      _yerel_id: o.id,
      istasyon_id: o.istasyon_id,
      ph: o.ph,
      serbest_klor: o.serbest_klor,
      bulaniklik: o.bulaniklik,
      iletkenlik: o.iletkenlik,
      sicaklik: o.sicaklik,
      personel_notu: o.personel_notu,
    }));

    // Toplu gönder
    const sonuclar = await topluOlcumGonder(apiGonderimi);

    // Başarılıları 'tamamlandi' yap
    for (const basarili of sonuclar.basarili) {
      await guncelleDurum(basarili.yerelId, "tamamlandi");
    }

    // Başarısızları 'hata' yap (tekrar denenebilsin)
    for (const basarisiz of sonuclar.basarisiz) {
      await guncelleDurum(basarisiz.yerelId, "bekliyor"); // tekrar dene
      console.warn(`[Sync] Ölçüm gönderilemedi (id=${basarisiz.yerelId}): ${basarisiz.hata}`);
    }

    // KRİTİK anomaliler için bildirim
    if (sonuclar.kritikOlanlar.length > 0) {
      console.warn(`[Sync] ${sonuclar.kritikOlanlar.length} KRİTİK anomali tespit edildi!`);
      for (const kritik of sonuclar.kritikOlanlar) {
        await kritikAnomalibildirimi(kritik.detaylar);
      }
    }

    // Özet bildirim
    const basariliSayisi = sonuclar.basarili.length;
    const basarisizSayisi = sonuclar.basarisiz.length;

    if (basariliSayisi > 0) {
      await senkronizasyonTamamlandiBildirimi(basariliSayisi, basarisizSayisi);
    }

    // Eski tamamlananları temizle
    await temizleTamamlananlar();

    const ozet = {
      basarili: basariliSayisi,
      basarisiz: basarisizSayisi,
      kritik: sonuclar.kritikOlanlar.length,
    };

    console.log("[Sync] Tamamlandı:", ozet);
    return ozet;

  } catch (error) {
    console.error("[Sync] Beklenmeyen hata:", error);
    return { basarili: 0, basarisiz: 0, kritik: 0, hata: error.message };
  } finally {
    _syncCalisiyorMu = false;
  }
}
