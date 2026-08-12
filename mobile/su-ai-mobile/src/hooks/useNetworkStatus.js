// hooks/useNetworkStatus.js
// Ağ durumunu ve offline sync işlemlerini yöneten hook

import { useState, useEffect, useCallback } from "react";
import NetInfo from "@react-native-community/netinfo";
import { getBekleyenOlcumler, guncelleDurum } from "../services/offlineStorage";
import { topluOlcumGonder } from "../services/api";
import { senkronizasyonTamamlandiBildirimi } from "../services/notificationService";

/**
 * Ağ bağlantısını izler ve bekleyen offline ölçümleri otomatik senkronize eder.
 *
 * @returns {{
 *   isOnline: boolean,
 *   syncDurumu: 'bosta' | 'senkronize_ediliyor' | 'tamamlandi' | 'hata',
 *   manuelSync: () => Promise<void>
 * }}
 */
export function useNetworkStatus() {
  const [isOnline, setIsOnline] = useState(true);
  const [syncDurumu, setSyncDurumu] = useState("bosta");

  // Bekleyen ölçümleri sunucuya gönder
  const sync = useCallback(async () => {
    try {
      const bekleyenler = await getBekleyenOlcumler();
      if (bekleyenler.length === 0) return;

      setSyncDurumu("senkronize_ediliyor");

      // Her birini gönderilebilir formata çevir (yerel id'yi ekle)
      const olcumListesi = bekleyenler.map((o) => ({
        ...o,
        _yerel_id: o.id,
      }));

      const sonuclar = await topluOlcumGonder(olcumListesi);

      // Başarılıları tamamlandı olarak işaretle
      for (const s of sonuclar.basarili) {
        await guncelleDurum(s.yerelId, "tamamlandi");
      }

      // Başarısızları hata olarak işaretle
      for (const s of sonuclar.basarisiz) {
        await guncelleDurum(s.yerelId, "hata");
      }

      if (sonuclar.basarili.length > 0) {
        await senkronizasyonTamamlandiBildirimi(sonuclar.basarili.length, sonuclar.basarisiz.length);
      }
      setSyncDurumu("tamamlandi");

      // 3 saniye sonra durumu sıfırla
      setTimeout(() => setSyncDurumu("bosta"), 3000);
    } catch (err) {
      console.warn("[useNetworkStatus] Sync hatası:", err.message);
      setSyncDurumu("hata");
      setTimeout(() => setSyncDurumu("bosta"), 5000);
    }
  }, []);

  useEffect(() => {
    // Başlangıç ağ durumunu al
    NetInfo.fetch().then((state) => {
      setIsOnline(state.isConnected ?? true);
    });

    // Ağ değişikliklerini dinle
    const unsubscribe = NetInfo.addEventListener((state) => {
      const online = state.isConnected ?? true;
      setIsOnline(online);

      // Bağlantı geri geldiğinde bekleyen ölçümleri otomatik gönder
      if (online) {
        sync();
      }
    });

    return () => unsubscribe();
  }, [sync]);

  return {
    isOnline,
    syncDurumu,
    manuelSync: sync,
  };
}
