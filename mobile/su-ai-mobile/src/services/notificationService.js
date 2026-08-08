// services/notificationService.js
// Su-AI Yerel Bildirim Servisi
// KRİTİK seviyeli anomaliler senkronize edildiğinde yerel bildirim tetikler.
//
// NOT: expo-notifications, Expo Go'da SDK 53+ itibarıyla desteklenmiyor.
// Expo Go'da modül hiç yüklenmez; tüm fonksiyonlar sessizce no-op olarak çalışır.

import Constants from "expo-constants";
import { Platform } from "react-native";

// Expo Go kontrolü — modül yüklenirken hemen yap
const IS_EXPO_GO =
  Constants.executionEnvironment === "storeClient" ||
  Constants.appOwnership === "expo";

// Expo Go dışında (dev/prod build) modülü yükle ve handler'ı kur
let Notifications = null;
if (!IS_EXPO_GO) {
  Notifications = require("expo-notifications");
  Notifications.setNotificationHandler({
    handleNotification: async () => ({
      shouldShowAlert: true,
      shouldPlaySound: true,
      shouldSetBadge: true,
    }),
  });
}

/**
 * Kullanıcıdan bildirim izni ister.
 * Expo Go'da izin alınamaz; false döner.
 * @returns {boolean} İzin verildi mi?
 */
export async function izinIste() {
  if (IS_EXPO_GO || !Notifications) return false;

  const { status: mevcutDurum } = await Notifications.getPermissionsAsync();
  if (mevcutDurum === "granted") return true;

  const { status } = await Notifications.requestPermissionsAsync();
  return status === "granted";
}

/**
 * KRİTİK anomali tespiti sonrası yerel bildirim gönderir.
 * @param {Array} kritikDetaylar - AnomaliDetayi listesi
 * @param {string} istasyonAdi - Hangi istasyonda anomali var
 */
export async function kritikAnomalibildirimi(
  kritikDetaylar = [],
  istasyonAdi = "Bilinmeyen"
) {
  if (IS_EXPO_GO || !Notifications) return;

  const izinVar = await izinIste();
  if (!izinVar) {
    console.warn("[Bildirim] İzin verilmedi.");
    return;
  }

  const anomaliSayisi = kritikDetaylar.length;
  const ilkMesaj = kritikDetaylar[0]?.mesaj || "Kritik anomali tespit edildi";

  await Notifications.scheduleNotificationAsync({
    content: {
      title: `⚠️ KRİTİK ANOMALİ — ${istasyonAdi}`,
      body:
        anomaliSayisi > 1
          ? `${anomaliSayisi} kritik anomali tespit edildi. İlk: ${ilkMesaj}`
          : ilkMesaj,
      data: {
        tip: "KRITIK_ANOMALI",
        istasyon: istasyonAdi,
        detaylar: kritikDetaylar,
      },
      color: "#FF3B30",
      channelId: "kritik-anomali",
    },
    trigger: null,
  });
}

/**
 * Senkronizasyon tamamlandı bildirimi (özet).
 * @param {number} basarili - Başarılı ölçüm sayısı
 * @param {number} basarisiz - Hatalı ölçüm sayısı
 */
export async function senkronizasyonTamamlandiBildirimi(basarili, basarisiz) {
  if (IS_EXPO_GO || !Notifications) return;

  const izinVar = await izinIste();
  if (!izinVar) return;

  await Notifications.scheduleNotificationAsync({
    content: {
      title:
        basarisiz > 0
          ? `Senkronizasyon Kısmen Tamamlandı`
          : `✅ Senkronizasyon Tamamlandı`,
      body:
        basarisiz > 0
          ? `${basarili} ölçüm gönderildi, ${basarisiz} ölçüm başarısız oldu.`
          : `${basarili} bekleyen ölçüm başarıyla gönderildi.`,
      channelId: "sync-bildirim",
    },
    trigger: null,
  });
}

/**
 * Android için bildirim kanallarını oluşturur.
 * Uygulama başlangıcında bir kez çağrılmalı.
 */
export async function kanallarOlustur() {
  if (IS_EXPO_GO || !Notifications || Platform.OS !== "android") return;

  await Notifications.setNotificationChannelAsync("kritik-anomali", {
    name: "Kritik Su Kalitesi Uyarıları",
    importance: Notifications.AndroidImportance.MAX,
    vibrationPattern: [0, 500, 250, 500],
    lightColor: "#FF3B30",
    sound: "default",
  });

  await Notifications.setNotificationChannelAsync("sync-bildirim", {
    name: "Senkronizasyon Bildirimleri",
    importance: Notifications.AndroidImportance.DEFAULT,
  });
}
