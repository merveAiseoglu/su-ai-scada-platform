// services/offlineStorage.js
// Su-AI Offline Depolama Servisi — expo-sqlite tabanlı
// Ölçümleri yerel SQLite veritabanında saklar ve senkronizasyon durumunu takip eder.

import * as SQLite from "expo-sqlite";

const DB_NAME = "su_ai_offline.db";
let _db = null;

/**
 * Veritabanı bağlantısını açar ve tabloları oluşturur (idempotent).
 */
async function getDB() {
  if (_db) return _db;
  _db = await SQLite.openDatabaseAsync(DB_NAME);
  await _db.execAsync(`
    PRAGMA journal_mode = WAL;
    CREATE TABLE IF NOT EXISTS bekleyen_olcumler (
      id            INTEGER PRIMARY KEY AUTOINCREMENT,
      istasyon_id   INTEGER NOT NULL,
      ph            REAL,
      serbest_klor  REAL,
      bulaniklik    REAL,
      iletkenlik    REAL,
      sicaklik      REAL,
      personel_notu TEXT,
      olusturulma   TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
      durum         TEXT NOT NULL DEFAULT 'bekliyor'
      -- durum: 'bekliyor' | 'gonderiliyor' | 'tamamlandi' | 'hata'
    );
  `);
  return _db;
}

// ---------------------------------------------------------------------------
// CRUD İşlemleri
// ---------------------------------------------------------------------------

/**
 * Yeni bir offline ölçüm kaydeder.
 * @returns {number} Oluşturulan kaydın yerel ID'si
 */
export async function kaydetOlcum(olcumData) {
  const db = await getDB();
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
}

/**
 * Senkronizasyon bekleyen tüm ölçümleri getirir.
 * @returns {Array} Bekleyen ölçümler listesi
 */
export async function getBekleyenOlcumler() {
  const db = await getDB();
  return await db.getAllAsync(
    `SELECT * FROM bekleyen_olcumler WHERE durum = 'bekliyor' ORDER BY olusturulma ASC`
  );
}

/**
 * Belirli bir ölçümün durumunu günceller.
 * @param {number} id - Yerel kayıt ID'si
 * @param {'bekliyor'|'gonderiliyor'|'tamamlandi'|'hata'} durum
 */
export async function guncelleDurum(id, durum) {
  const db = await getDB();
  await db.runAsync(
    `UPDATE bekleyen_olcumler SET durum = ? WHERE id = ?`,
    [durum, id]
  );
}

/**
 * Tamamlanan ölçümleri temizler (7 günden eski).
 */
export async function temizleTamamlananlar() {
  const db = await getDB();
  await db.runAsync(
    `DELETE FROM bekleyen_olcumler
     WHERE durum = 'tamamlandi'
       AND olusturulma < datetime('now', '-7 days', 'localtime')`
  );
}

/**
 * Bekleyen ölçüm sayısını döner (UI badge için).
 */
export async function getBekleyenSayisi() {
  const db = await getDB();
  const row = await db.getFirstAsync(
    `SELECT COUNT(*) as sayi FROM bekleyen_olcumler WHERE durum = 'bekliyor'`
  );
  return row?.sayi ?? 0;
}
