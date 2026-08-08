// services/api.js
// Su-AI Backend API Katmanı
// Backend sunucu IP adresi — fiziksel cihaz/emülatör erişimi için güncellendi.

// ÖNEMLİ: Sunucu IP'si değiştiğinde aşağıdaki BASE_URL'yi güncelleyin.
export const API_URL = "http://192.168.1.102:8000";
const BASE_URL = API_URL;

let cachedToken = null;

export async function getToken() {
  return cachedToken;
}

/**
 * Kullanıcı girişi yapar ve token'ı hafızada tutar.
 */
export async function login(email, password) {
  const formData = new URLSearchParams();
  formData.append("username", email);
  formData.append("password", password);
  
  const response = await fetch(`${BASE_URL}/token`, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: formData.toString()
  });

  if (response.ok) {
    const data = await response.json();
    cachedToken = data.access_token;
    return true;
  } else {
    const errorData = await response.json();
    throw new Error(errorData.detail || "Giriş başarısız");
  }
}

/**
 * Oturumu kapatır ve token'ı temizler.
 */
export async function logout() {
  cachedToken = null;
}

/**
 * Temel fetch wrapper — hata yönetimi ve JSON parse dahil
 */
async function apiRequest(path, options = {}) {
  const url = `${BASE_URL}${path}`;
  const token = await getToken();
  const config = {
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...(token ? { "Authorization": `Bearer ${token}` } : {}),
      ...options.headers,
    },
    ...options,
  };

  try {
    const response = await fetch(url, config);

    // Boş gövde kontrolü — 204 No Content veya boş dönüşler için güvenli parse
    let data;
    const contentType = response.headers.get("content-type") || "";
    const text = await response.text();
    try {
      data = text ? JSON.parse(text) : {};
    } catch {
      data = {};
    }

    if (!response.ok) {
      throw new Error(data.detail || `HTTP ${response.status} hatası`);
    }
    return data;
  } catch (error) {
    if (
      error.message.includes("Network request failed") ||
      error.message.includes("fetch")
    ) {
      throw new Error("NETWORK_ERROR");
    }
    throw error;
  }
}

// ---------------------------------------------------------------------------
// İstasyon API'leri
// ---------------------------------------------------------------------------

/** Tüm aktif istasyonları getirir */
export async function getIstasyonlar() {
  return apiRequest("/istasyonlar/");
}

/** GIS için istasyon koordinatlarını getirir */
export async function getGisIstasyonlar() {
  return apiRequest("/api/gis/istasyonlar");
}

/** Tek bir istasyonu ID ile getirir */
export async function getIstasyon(id) {
  return apiRequest(`/istasyonlar/${id}`);
}

// ---------------------------------------------------------------------------
// Ölçüm API'leri
// ---------------------------------------------------------------------------

/**
 * Tek bir ölçümü ID ile getirir — analiz_durumu polling için kullanılır.
 * @param {number} olcumId
 */
export async function getOlcum(olcumId) {
  return apiRequest(`/olcumler/${olcumId}`);
}

/**
 * Yeni ölçüm gönderir — kural motoru sonucunu response içinde döner.
 * Backend LLM'i arka plana atar; analiz_durumu="BEKLİYOR" ile anında döner.
 * @param {Object} olcumData - { istasyon_id, ph, serbest_klor, bulaniklik, iletkenlik, sicaklik }
 */
export async function postOlcum(olcumData) {
  return apiRequest("/su-olcumu", {
    method: "POST",
    body: JSON.stringify(olcumData),
  });
}

/**
 * LLM aksiyon önerisi getirir (analiz sonucu + teknik öneri).
 * @param {number} olcumId - Daha önce kaydedilen ölçümün ID'si
 */
export async function getAksiyonOnerisi(olcumId) {
  return apiRequest(`/su-olcumu/${olcumId}/aksiyon-onerisi`);
}

/**
 * Birden fazla ölçümü sırayla gönderir (offline sync için).
 * Başarılı ve başarısız olanları ayırarak raporlar.
 * @param {Array} olcumListesi - postOlcum'a uyumlu obje listesi
 */
export async function topluOlcumGonder(olcumListesi) {
  const sonuclar = {
    basarili: [],
    basarisiz: [],
    kritikOlanlar: [],
  };

  for (const olcum of olcumListesi) {
    try {
      const response = await postOlcum(olcum);
      sonuclar.basarili.push({ yerelId: olcum._yerel_id, sunucuId: response.id, response });

      // Risk kontrolü — KRİTİK olanları bildirim için işaretle
      if (response.analiz_sonucu?.en_yuksek_risk_seviyesi === "KRİTİK") {
        sonuclar.kritikOlanlar.push({
          yerelId: olcum._yerel_id,
          sunucuId: response.id,
          detaylar: response.analiz_sonucu.detaylar,
        });
      }
    } catch (error) {
      sonuclar.basarisiz.push({
        yerelId: olcum._yerel_id,
        hata: error.message,
      });
    }
  }

  return sonuclar;
}

// ---------------------------------------------------------------------------
// Son Ölçümler — SimulatorScreen ve dashboard için
// ---------------------------------------------------------------------------

/**
 * Son ölçümleri listeler (isteğe bağlı istasyon filtresi ve limit).
 * @param {number} [limit=20]
 * @param {number|null} [istasyonId=null]
 */
export async function getSonOlcumler(limit = 20, istasyonId = null) {
  let path = `/olcumler/?limit=${limit}`;
  if (istasyonId != null) path += `&istasyon_id=${istasyonId}`;
  return apiRequest(path);
}

// ---------------------------------------------------------------------------
// Faz 4 — Simülatör API'leri (sadece yönetici)
// ---------------------------------------------------------------------------

/** Simülatör durum bilgisini getirir (toplam tetikleme, son zaman). */
export async function getSimDurum() {
  return apiRequest("/api/sim/durum");
}

/**
 * Tek bir simüle ölçümü anında tetikler.
 * @param {number} [istasyonId=1]
 * @param {'normal'|'anomali'|'karisik'} [mod='karisik']
 */
export async function postSimTetikle(istasyonId = 1, mod = "karisik") {
  return apiRequest(
    `/api/sim/tetikle?istasyon_id=${istasyonId}&mod=${mod}`,
    { method: "POST" }   // body yok — FastAPI query param okuyor
  );
}

// ---------------------------------------------------------------------------
// Faz 2 — Audit Log & Yetkilendirme API'leri
// ---------------------------------------------------------------------------

/**
 * JWT token içindeki bilgileri (email, rol) decode eder.
 */
export async function getUserInfo() {
  const token = await getToken();
  if (!token) return null;
  try {
    // JWT formatı: header.payload.signature
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    // Buffer veya atob yerine basit JSON parse
    const jsonPayload = decodeURIComponent(atob(base64).split('').map(function(c) {
        return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
    }).join(''));

    return JSON.parse(jsonPayload);
  } catch (e) {
    console.error("Token decode hatası:", e);
    return null;
  }
}

/**
 * Son denetim izi (audit log) kayıtlarını getirir.
 * Sadece 'yonetici' rolü kullanabilir.
 */
export async function getAuditLogs(limit = 100) {
  return apiRequest(`/audit-logs/?limit=${limit}`);
}
