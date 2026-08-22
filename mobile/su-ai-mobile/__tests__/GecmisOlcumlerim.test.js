// __tests__/GecmisOlcumlerim.test.js
// Client-side filtreleme, 5 parametreli kart formatı ve sayfalama doğrulama testi (Node.js test runner)
const { test, describe } = require("node:test");
const assert = require("node:assert");

const FILTRELER = ["TÜMÜ", "NORMAL", "DÜŞÜK", "ORTA", "KRİTİK"];

function filterOlcumler(olcumler, seciliFiltre) {
  if (seciliFiltre === "TÜMÜ") return olcumler;
  return olcumler.filter((item) => item.risk_seviyesi === seciliFiltre);
}

function formatOlcumParametreleri(item) {
  const params = [];
  if (item.ph != null) params.push({ key: "ph", label: `pH: ${item.ph}`, ikon: "water-outline" });
  if (item.serbest_klor != null) params.push({ key: "klor", label: `Klor: ${item.serbest_klor} mg/L`, ikon: "flask-outline" });
  if (item.bulaniklik != null) params.push({ key: "bulaniklik", label: `Bulanıklık: ${item.bulaniklik} NTU`, ikon: "blur" });
  if (item.iletkenlik != null) params.push({ key: "iletkenlik", label: `İletkenlik: ${item.iletkenlik} µS/cm`, ikon: "flash-outline" });
  if (item.sicaklik != null) params.push({ key: "sicaklik", label: `Sıcaklık: ${item.sicaklik} °C`, ikon: "thermometer" });
  return params;
}

function buildGetSonOlcumlerPath(limit = 20, istasyonId = null, offset = 0) {
  let path = `/olcumler/?limit=${limit}&offset=${offset}`;
  if (istasyonId != null) path += `&istasyon_id=${istasyonId}`;
  return path;
}

function paginateData(allRecords, limit, offset) {
  return allRecords.slice(offset, offset + limit);
}

describe("GecmisOlcumlerimScreen Filtreleme Mantığı", () => {
  const mockData = [
    { id: 1, istasyon_id: 1, risk_seviyesi: "NORMAL", ph: 7.4, iletkenlik: 350, sicaklik: 19.5 },
    { id: 2, istasyon_id: 1, risk_seviyesi: "NORMAL", ph: 7.2, iletkenlik: 400, sicaklik: 20.0 },
    { id: 3, istasyon_id: 2, risk_seviyesi: "DÜŞÜK", ph: 6.8, serbest_klor: 0.2 },
    { id: 4, istasyon_id: 2, risk_seviyesi: "ORTA", ph: 6.3, bulaniklik: 2.1 },
    { id: 5, istasyon_id: 3, risk_seviyesi: "KRİTİK", ph: 4.1, iletkenlik: 950, sicaklik: 28.0 },
    { id: 6, istasyon_id: 3, risk_seviyesi: "KRİTİK", ph: 10.2, serbest_klor: 0.01 },
  ];

  test("TÜMÜ seçildiğinde tüm kayıtlar döner", () => {
    const result = filterOlcumler(mockData, "TÜMÜ");
    assert.strictEqual(result.length, 6);
  });

  test("NORMAL seçildiğinde sadece NORMAL risk seviyesindekiler döner", () => {
    const result = filterOlcumler(mockData, "NORMAL");
    assert.strictEqual(result.length, 2);
    assert.ok(result.every((r) => r.risk_seviyesi === "NORMAL"));
  });

  test("DÜŞÜK seçildiğinde sadece DÜŞÜK risk seviyesindekiler döner", () => {
    const result = filterOlcumler(mockData, "DÜŞÜK");
    assert.strictEqual(result.length, 1);
    assert.strictEqual(result[0].id, 3);
    assert.strictEqual(result[0].risk_seviyesi, "DÜŞÜK");
  });

  test("ORTA seçildiğinde sadece ORTA risk seviyesindekiler döner", () => {
    const result = filterOlcumler(mockData, "ORTA");
    assert.strictEqual(result.length, 1);
    assert.strictEqual(result[0].id, 4);
    assert.strictEqual(result[0].risk_seviyesi, "ORTA");
  });

  test("KRİTİK seçildiğinde sadece KRİTİK risk seviyesindekiler döner", () => {
    const result = filterOlcumler(mockData, "KRİTİK");
    assert.strictEqual(result.length, 2);
    assert.ok(result.every((r) => r.risk_seviyesi === "KRİTİK"));
  });
});

describe("GecmisOlcumlerimScreen 5 Parametre Kart Formatı (pH, Klor, Bulanıklık, İletkenlik, Sıcaklık)", () => {
  test("5 parametrenin tümü mevcut olduğunda eksiksiz etiket ve birimlerle üretilir", () => {
    const item = {
      ph: 7.35,
      serbest_klor: 0.85,
      bulaniklik: 0.42,
      iletkenlik: 420.5,
      sicaklik: 21.3
    };
    const params = formatOlcumParametreleri(item);
    assert.strictEqual(params.length, 5);
    
    assert.strictEqual(params[0].label, "pH: 7.35");
    assert.strictEqual(params[1].label, "Klor: 0.85 mg/L");
    assert.strictEqual(params[2].label, "Bulanıklık: 0.42 NTU");
    assert.strictEqual(params[3].label, "İletkenlik: 420.5 µS/cm");
    assert.strictEqual(params[4].label, "Sıcaklık: 21.3 °C");
  });

  test("İletkenlik ve Sıcaklık ikonları flash-outline ve thermometer olarak atanır", () => {
    const item = { iletkenlik: 500, sicaklik: 18.0 };
    const params = formatOlcumParametreleri(item);
    assert.strictEqual(params.length, 2);
    assert.strictEqual(params[0].ikon, "flash-outline");
    assert.strictEqual(params[1].ikon, "thermometer");
  });

  test("Null veya undefined değerler filtrelenir", () => {
    const item = { ph: 7.1, serbest_klor: null, bulaniklik: undefined, iletkenlik: 320, sicaklik: null };
    const params = formatOlcumParametreleri(item);
    assert.strictEqual(params.length, 2);
    assert.strictEqual(params[0].key, "ph");
    assert.strictEqual(params[1].key, "iletkenlik");
  });
});

describe("GecmisOlcumlerimScreen Sayfalama & Offset Mantığı", () => {
  test("buildGetSonOlcumlerPath limit ve offset parametrelerini doğru üretir", () => {
    assert.strictEqual(buildGetSonOlcumlerPath(50, null, 0), "/olcumler/?limit=50&offset=0");
    assert.strictEqual(buildGetSonOlcumlerPath(50, null, 50), "/olcumler/?limit=50&offset=50");
    assert.strictEqual(buildGetSonOlcumlerPath(20, 3, 40), "/olcumler/?limit=20&offset=40&istasyon_id=3");
  });

  test("Sayfalama ve sonsuz kaydırma ile kayıtlar sırayla birleşir", () => {
    const totalRecords = Array.from({ length: 120 }, (_, i) => ({ id: i + 1, ph: 7.0 }));
    
    // Page 1
    const page1 = paginateData(totalRecords, 50, 0);
    assert.strictEqual(page1.length, 50);
    assert.strictEqual(page1[0].id, 1);
    assert.strictEqual(page1[49].id, 50);

    // Page 2
    const page2 = paginateData(totalRecords, 50, 50);
    assert.strictEqual(page2.length, 50);
    assert.strictEqual(page2[0].id, 51);
    assert.strictEqual(page2[49].id, 100);

    // Page 3 (Son sayfa)
    const page3 = paginateData(totalRecords, 50, 100);
    assert.strictEqual(page3.length, 20);
    assert.strictEqual(page3[0].id, 101);
    assert.strictEqual(page3[19].id, 120);

    // Birleşen liste
    let accumulated = [...page1];
    accumulated = [...accumulated, ...page2];
    accumulated = [...accumulated, ...page3];
    assert.strictEqual(accumulated.length, 120);
  });
});

describe("GecmisOlcumlerimScreen Offline SQLite Birleştirme ve ID/Deduplication Mantığı", () => {
  function mergeAndSortOlcumler(yerelVeriler, sunucuVerileri) {
    const yerelFormatli = (yerelVeriler || []).map((y) => ({
      id: `local_${y.id}`,
      _isLocal: true,
      _durum: y.durum,
      _yerelId: y.id,
      istasyon_id: y.istasyon_id,
      ph: y.ph,
      serbest_klor: y.serbest_klor,
      bulaniklik: y.bulaniklik,
      iletkenlik: y.iletkenlik,
      sicaklik: y.sicaklik,
      olcum_tarihi: y.olusturulma ? new Date(y.olusturulma.replace(" ", "T")).toISOString() : new Date().toISOString(),
      risk_seviyesi: null,
    }));

    const sunucuListesi = sunucuVerileri || [];
    const birlesik = [...yerelFormatli, ...sunucuListesi];
    birlesik.sort((a, b) => new Date(b.olcum_tarihi) - new Date(a.olcum_tarihi));
    return birlesik;
  }

  test("Yerel çevrimdışı kayıtlar ve sunucu kayıtları tarihe göre doğru birleşir ve sıralanır", () => {
    const yerel = [
      { id: 1, istasyon_id: 10, ph: 7.2, olusturulma: "2026-08-17T18:30:00Z", durum: "bekliyor" },
      { id: 2, istasyon_id: 11, ph: 6.8, olusturulma: "2026-08-17T18:40:00Z", durum: "gonderiliyor" },
    ];
    const sunucu = [
      { id: 101, istasyon_id: 10, ph: 7.5, risk_seviyesi: "NORMAL", olcum_tarihi: "2026-08-17T18:35:00Z" },
      { id: 100, istasyon_id: 10, ph: 6.4, risk_seviyesi: "KRİTİK", olcum_tarihi: "2026-08-17T18:00:00Z" },
    ];

    const result = mergeAndSortOlcumler(yerel, sunucu);
    assert.strictEqual(result.length, 4);

    // En yeni tarih en üstte olmalı:
    // 18:40 (local_2) -> 18:35 (server 101) -> 18:30 (local_1) -> 18:00 (server 100)
    assert.strictEqual(result[0].id, "local_2");
    assert.strictEqual(result[0]._isLocal, true);
    assert.strictEqual(result[0]._durum, "gonderiliyor");

    assert.strictEqual(result[1].id, 101);
    assert.strictEqual(result[1]._isLocal, undefined);

    assert.strictEqual(result[2].id, "local_1");
    assert.strictEqual(result[2]._isLocal, true);

    assert.strictEqual(result[3].id, 100);
  });

  test("Senkronize edilen yerel kayıt SQLite'ta tamamlandi olduğunda sunucu listesinde yer alır ve yinelenmez", () => {
    // Sync sonrası: SQLite'taki kayıt tamamlandi oldu ve sunucu GET /olcumler/ listesine eklendi
    const yerelKalanlar = []; // tamamlandi olanlar getSenkronizeEdilmemisOlcumler ile gelmez
    const sunucuGuncel = [
      { id: 102, istasyon_id: 11, ph: 6.8, risk_seviyesi: "NORMAL", olcum_tarihi: "2026-08-17T18:40:00Z" },
      { id: 101, istasyon_id: 10, ph: 7.5, risk_seviyesi: "NORMAL", olcum_tarihi: "2026-08-17T18:35:00Z" },
    ];

    const result = mergeAndSortOlcumler(yerelKalanlar, sunucuGuncel);
    assert.strictEqual(result.length, 2);
    assert.strictEqual(result[0].id, 102);
    assert.strictEqual(result[0].risk_seviyesi, "NORMAL");
    assert.ok(!result.some(r => r._isLocal));
  });
});

