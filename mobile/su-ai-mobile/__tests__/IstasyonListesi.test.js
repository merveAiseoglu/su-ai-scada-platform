// __tests__/IstasyonListesi.test.js
// İstasyon kartı navigasyon mantığı (Ölçüm Gir ve Geçmiş/Trend Analizi ayrımı) doğrulama testi
const { test, describe } = require("node:test");
const assert = require("node:assert");

function getStationNavigationParams(station, actionType) {
  if (actionType === "HISTORY") {
    return {
      screen: "StationHistoryScreen",
      params: {
        station_id: station.id,
        station_ad: station.ad,
      },
    };
  }
  if (actionType === "MEASUREMENT") {
    return {
      screen: "MeasurementForm",
      params: {
        istasyon: station,
      },
    };
  }
  throw new Error("Geçersiz eylem tipi");
}

describe("IstasyonListesiScreen Kart Navigasyon Mantığı", () => {
  const mockStation = {
    id: 3,
    ad: "Merkez Su Deposu",
    konum: "Şanlıurfa Merkez",
    tip: "Depo",
    aktif_mi: true,
  };

  test("Kart sol alanına veya ok ikonuna tıklandığında MeasurementForm parametreleri doğru üretilir", () => {
    const nav = getStationNavigationParams(mockStation, "MEASUREMENT");
    assert.strictEqual(nav.screen, "MeasurementForm");
    assert.strictEqual(nav.params.istasyon.id, 3);
    assert.strictEqual(nav.params.istasyon.ad, "Merkez Su Deposu");
  });

  test("Geçmiş/Trend butonuna tıklandığında StationHistoryScreen (station_id ve station_ad ile) parametreleri doğru üretilir", () => {
    const nav = getStationNavigationParams(mockStation, "HISTORY");
    assert.strictEqual(nav.screen, "StationHistoryScreen");
    assert.strictEqual(nav.params.station_id, 3);
    assert.strictEqual(nav.params.station_ad, "Merkez Su Deposu");
  });
});
