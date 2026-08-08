// hooks/useNetworkStatus.js
// Ağ durumunu izleyen ve otomatik sync tetikleyen custom hook.

import { useState, useEffect, useRef, useCallback } from "react";
import NetInfo from "@react-native-community/netinfo";
import { senkronizeEt } from "../services/syncService";

/**
 * Ağ durumunu izler ve online'a geçildiğinde otomatik olarak
 * bekleyen offline ölçümleri senkronize eder.
 *
 * @returns {{ isOnline: boolean, syncDurumu: object|null, manuelSync: Function }}
 */
export function useNetworkStatus() {
  const [isOnline, setIsOnline] = useState(true);
  const [syncDurumu, setSyncDurumu] = useState(null);
  const oncekiDurumRef = useRef(true); // Önceki online durumunu takip et

  const manuelSync = useCallback(async () => {
    if (!isOnline) {
      console.log("[NetworkHook] Çevrimdışı — manuel sync atlandı.");
      return null;
    }
    setSyncDurumu({ durum: "calisıyor" });
    const sonuc = await senkronizeEt();
    setSyncDurumu(sonuc);
    return sonuc;
  }, [isOnline]);

  useEffect(() => {
    // NetInfo aboneliği
    const abonelikIptal = NetInfo.addEventListener(async (state) => {
      const simdiOnline = state.isConnected && state.isInternetReachable !== false;
      setIsOnline(simdiOnline);

      // Offline → Online geçişinde otomatik sync tetikle
      if (simdiOnline && !oncekiDurumRef.current) {
        console.log("[NetworkHook] Online'a geçildi — otomatik sync başlatılıyor...");
        setSyncDurumu({ durum: "calisıyor" });
        const sonuc = await senkronizeEt();
        setSyncDurumu(sonuc);
      }

      oncekiDurumRef.current = simdiOnline;
    });

    return () => abonelikIptal(); // Cleanup
  }, []);

  return { isOnline, syncDurumu, manuelSync };
}
