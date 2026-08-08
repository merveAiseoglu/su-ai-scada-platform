// screens/SimulatorScreen.js
// Faz 4 — IoT Simülasyon Takip Ekranı
// Son simüle ölçümleri gösterir, tek tetikleme butonuna sahip.

import React, { useState, useEffect, useCallback, useRef } from "react";
import {
  View, Text, FlatList, TouchableOpacity, StyleSheet,
  ActivityIndicator, Alert, RefreshControl, Animated,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { MaterialCommunityIcons } from "@expo/vector-icons";
import { getSonOlcumler, getSimDurum, postSimTetikle, getGisIstasyonlar } from "../services/api";

// ---------------------------------------------------------------------------
// Risk → renk eşleşmesi
// ---------------------------------------------------------------------------
const RISK_STIL = {
  KRİTİK: { renk: "#E74C3C", bg: "#FDEDEC", ikon: "alert-circle" },
  ORTA:   { renk: "#E67E22", bg: "#FEF9E7", ikon: "alert" },
  DÜŞÜK:  { renk: "#F39C12", bg: "#FFFDE7", ikon: "information" },
  NORMAL: { renk: "#27AE60", bg: "#EAFAF1", ikon: "check-circle" },
};
function getRiskStil(risk) {
  return RISK_STIL[risk] || RISK_STIL["NORMAL"];
}

// ---------------------------------------------------------------------------
// Tek ölçüm kartı
// ---------------------------------------------------------------------------
function OlcumKart({ item, istasyonlar }) {
  const stil = getRiskStil(item.risk_seviyesi);
  const istasyon = istasyonlar.find(i => i.id === item.istasyon_id);
  const tarih = item.olcum_tarihi
    ? new Date(item.olcum_tarihi).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit", second: "2-digit" })
    : "—";
  const simMi = item.personel_notu?.startsWith("[SIM:");

  return (
    <View style={[styles.kart, { borderLeftColor: stil.renk, borderLeftWidth: 4 }]}>
      {/* Üst satır */}
      <View style={styles.kartUst}>
        <View style={styles.kartSol}>
          <MaterialCommunityIcons name={stil.ikon} size={20} color={stil.renk} />
          <Text style={styles.kartIstasyon} numberOfLines={1}>
            {istasyon?.ad || `İstasyon #${item.istasyon_id}`}
          </Text>
        </View>
        <View style={styles.kartSag}>
          {simMi && (
            <View style={styles.simBadge}>
              <Text style={styles.simBadgeText}>SIM</Text>
            </View>
          )}
          <View style={[styles.riskBadge, { backgroundColor: stil.bg }]}>
            <Text style={[styles.riskText, { color: stil.renk }]}>
              {item.risk_seviyesi || "NORMAL"}
            </Text>
          </View>
        </View>
      </View>

      {/* Sensör değerleri */}
      <View style={styles.sensorSatir}>
        {item.ph        != null && <Text style={styles.sensor}>pH {item.ph?.toFixed(2)}</Text>}
        {item.serbest_klor != null && <Text style={styles.sensor}>Cl {item.serbest_klor?.toFixed(2)}</Text>}
        {item.bulaniklik != null && <Text style={styles.sensor}>NTU {item.bulaniklik?.toFixed(1)}</Text>}
        {item.iletkenlik != null && <Text style={styles.sensor}>µS {item.iletkenlik?.toFixed(0)}</Text>}
        {item.sicaklik   != null && <Text style={styles.sensor}>{item.sicaklik?.toFixed(1)}°C</Text>}
      </View>

      {/* Tarih */}
      <Text style={styles.kartTarih}>🕐 {tarih}</Text>
    </View>
  );
}

// ---------------------------------------------------------------------------
// Ana ekran
// ---------------------------------------------------------------------------
export default function SimulatorScreen({ navigation }) {
  const [olcumler, setOlcumler] = useState([]);
  const [istasyonlar, setIstasyonlar] = useState([]);
  const [simDurum, setSimDurum] = useState(null);
  const [yukleniyor, setYukleniyor] = useState(true);
  const [yenileniyor, setYenileniyor] = useState(false);
  const [tetikleniyorMod, setTetikleniyorMod] = useState(null); // null | 'normal' | 'anomali' | 'karisik'

  // Pulse animasyon (tetikleme butonu için)
  const pulseAnim = useRef(new Animated.Value(1)).current;

  const veriYukle = useCallback(async (sessiz = false) => {
    if (!sessiz) setYukleniyor(true);
    try {
      const [olcumVerisi, istVeri, durumVerisi] = await Promise.allSettled([
        getSonOlcumler(30),
        getGisIstasyonlar(),
        getSimDurum(),
      ]);

      if (olcumVerisi.status === "fulfilled") setOlcumler(olcumVerisi.value);
      if (istVeri.status     === "fulfilled") setIstasyonlar(istVeri.value);
      if (durumVerisi.status === "fulfilled") setSimDurum(durumVerisi.value);
    } catch (e) {
      // Sessiz hatalar
    } finally {
      setYukleniyor(false);
      setYenileniyor(false);
    }
  }, []);

  useEffect(() => {
    veriYukle();
    // 15 saniyede bir otomatik yenile
    const interval = setInterval(() => veriYukle(true), 15000);
    return () => clearInterval(interval);
  }, [veriYukle]);

  const tetikle = async (mod) => {
    setTetikleniyorMod(mod);

    // Pulse animasyonu
    Animated.sequence([
      Animated.timing(pulseAnim, { toValue: 0.9, duration: 100, useNativeDriver: true }),
      Animated.timing(pulseAnim, { toValue: 1.0, duration: 200, useNativeDriver: true }),
    ]).start();

    try {
      // İlk aktif istasyonu bul
      const istId = istasyonlar.find(i => i.aktif_mi)?.id || 1;
      const yanit = await postSimTetikle(istId, mod);
      const risk = yanit.risk_seviyesi || "NORMAL";
      const renkler = { KRİTİK: "🔴", ORTA: "🟠", DÜŞÜK: "🟡", NORMAL: "🟢" };

      Alert.alert(
        "Simülasyon Ölçümü Gönderildi",
        `${renkler[risk] || "🔵"} Risk: ${risk}\n` +
        `pH: ${yanit.ph?.toFixed(2)}\n` +
        `Cl: ${yanit.serbest_klor?.toFixed(2)} mg/L\n` +
        `NTU: ${yanit.bulaniklik?.toFixed(1)}`
      );

      // Listeyi güncelle
      setTimeout(() => veriYukle(true), 500);
    } catch (e) {
      Alert.alert("Hata", e.message === "NETWORK_ERROR"
        ? "Sunucuya bağlanılamadı."
        : e.message);
    } finally {
      setTetikleniyorMod(null);
    }
  };

  const kritikSayisi = olcumler.filter(o => o.risk_seviyesi === "KRİTİK").length;

  return (
    <SafeAreaView style={styles.kapsayici}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity style={styles.backBtn} onPress={() => navigation.goBack()}>
          <MaterialCommunityIcons name="arrow-left" size={24} color="#0056b3" />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={styles.headerBaslik}>IoT Simülatörü</Text>
          <Text style={styles.headerAlt}>Faz 4 — Veri Akışı Takibi</Text>
        </View>
        <TouchableOpacity onPress={() => { setYenileniyor(true); veriYukle(); }}>
          <MaterialCommunityIcons name="refresh" size={24} color="#0056b3" />
        </TouchableOpacity>
      </View>

      {/* Durum Kartı */}
      {simDurum && (
        <View style={styles.durumKart}>
          <View style={styles.durumSatir}>
            <MaterialCommunityIcons name="lightning-bolt" size={18} color="#0056b3" />
            <Text style={styles.durumMetin}>
              Toplam tetikleme:{" "}
              <Text style={styles.durumDeger}>{simDurum.toplam_tetikleme}</Text>
            </Text>
          </View>
          {simDurum.son_tetikle && (
            <Text style={styles.durumAlt}>
              Son: {new Date(simDurum.son_tetikle).toLocaleTimeString("tr-TR")}
            </Text>
          )}
          {kritikSayisi > 0 && (
            <View style={styles.kritikUyari}>
              <MaterialCommunityIcons name="alert-circle" size={14} color="#E74C3C" />
              <Text style={styles.kritikUyariText}>
                Son {olcumler.length} ölçümde {kritikSayisi} KRİTİK
              </Text>
            </View>
          )}
        </View>
      )}

      {/* Tetikleme Butonları */}
      <View style={styles.butonlar}>
        <Text style={styles.butonBaslik}>Tek Ölçüm Tetikle</Text>
        <View style={styles.butonSatir}>
          {[
            { mod: "normal",  label: "Normal",   renk: "#27AE60", ikon: "check-circle-outline" },
            { mod: "anomali", label: "Anomali",  renk: "#E74C3C", ikon: "alert-circle-outline" },
            { mod: "karisik", label: "Karışık",  renk: "#0056b3", ikon: "shuffle-variant" },
          ].map(({ mod, label, renk, ikon }) => (
            <Animated.View key={mod} style={{ transform: [{ scale: tetikleniyorMod === mod ? pulseAnim : 1 }] }}>
              <TouchableOpacity
                style={[styles.tetikleBtn, { borderColor: renk, backgroundColor: tetikleniyorMod === mod ? renk : "#FFF" }]}
                onPress={() => tetikle(mod)}
                disabled={tetikleniyorMod !== null}
              >
                {tetikleniyorMod === mod
                  ? <ActivityIndicator size="small" color="#FFF" />
                  : <MaterialCommunityIcons name={ikon} size={18} color={renk} />
                }
                <Text style={[styles.tetikleBtnText, { color: tetikleniyorMod === mod ? "#FFF" : renk }]}>
                  {label}
                </Text>
              </TouchableOpacity>
            </Animated.View>
          ))}
        </View>
      </View>

      {/* Liste Başlığı */}
      <View style={styles.listeBaslik}>
        <Text style={styles.listeBaslikText}>Son Ölçümler</Text>
        <Text style={styles.listeBaslikAlt}>{olcumler.length} kayıt · 15sn'de yenilenir</Text>
      </View>

      {/* Ölçüm Listesi */}
      {yukleniyor ? (
        <View style={styles.yukleniyorBox}>
          <ActivityIndicator size="large" color="#0056b3" />
          <Text style={styles.yukleniyorText}>Yükleniyor...</Text>
        </View>
      ) : (
        <FlatList
          data={olcumler}
          keyExtractor={(item) => item.id.toString()}
          renderItem={({ item }) => <OlcumKart item={item} istasyonlar={istasyonlar} />}
          contentContainerStyle={styles.liste}
          showsVerticalScrollIndicator={false}
          refreshControl={
            <RefreshControl
              refreshing={yenileniyor}
              onRefresh={() => { setYenileniyor(true); veriYukle(); }}
              tintColor="#0056b3"
            />
          }
          ListEmptyComponent={
            <View style={styles.bosBox}>
              <MaterialCommunityIcons name="database-off" size={48} color="#CCC" />
              <Text style={styles.bosText}>Henüz ölçüm yok</Text>
              <Text style={styles.bosAlt}>Yukarıdaki butonlardan ölçüm tetikleyin</Text>
            </View>
          }
        />
      )}
    </SafeAreaView>
  );
}

// ---------------------------------------------------------------------------
// Stiller
// ---------------------------------------------------------------------------
const styles = StyleSheet.create({
  kapsayici:     { flex: 1, backgroundColor: "#F8F9FA" },
  header: {
    flexDirection: "row", alignItems: "center",
    paddingHorizontal: 16, paddingVertical: 12,
    backgroundColor: "#FFF",
    borderBottomWidth: 1, borderBottomColor: "rgba(0,0,0,0.07)",
    shadowColor: "#000", shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06, shadowRadius: 4, elevation: 3,
  },
  backBtn:        { padding: 6, marginRight: 10 },
  headerBaslik:   { fontSize: 18, fontWeight: "700", color: "#0056b3" },
  headerAlt:      { fontSize: 11, color: "#888", marginTop: 1 },

  durumKart: {
    margin: 12, padding: 14, borderRadius: 12,
    backgroundColor: "#EEF4FF",
    borderWidth: 1, borderColor: "#C5D8FF",
  },
  durumSatir:     { flexDirection: "row", alignItems: "center", gap: 6, marginBottom: 3 },
  durumMetin:     { fontSize: 13, color: "#555" },
  durumDeger:     { fontWeight: "700", color: "#0056b3" },
  durumAlt:       { fontSize: 11, color: "#888" },
  kritikUyari: {
    flexDirection: "row", alignItems: "center", gap: 4,
    marginTop: 6, backgroundColor: "#FDEDEC",
    borderRadius: 6, paddingHorizontal: 8, paddingVertical: 3,
    alignSelf: "flex-start",
  },
  kritikUyariText: { fontSize: 11, color: "#E74C3C", fontWeight: "600" },

  butonlar: {
    marginHorizontal: 12, marginBottom: 6,
    backgroundColor: "#FFF", borderRadius: 12,
    padding: 14, borderWidth: 1, borderColor: "rgba(0,0,0,0.06)",
  },
  butonBaslik:    { fontSize: 12, fontWeight: "600", color: "#888", marginBottom: 10, letterSpacing: 0.4 },
  butonSatir:     { flexDirection: "row", gap: 8 },
  tetikleBtn: {
    flex: 1, flexDirection: "row", alignItems: "center", justifyContent: "center",
    gap: 5, paddingVertical: 10, borderRadius: 10,
    borderWidth: 1.5,
  },
  tetikleBtnText: { fontSize: 12, fontWeight: "700" },

  listeBaslik: {
    flexDirection: "row", justifyContent: "space-between", alignItems: "baseline",
    paddingHorizontal: 16, paddingVertical: 8,
  },
  listeBaslikText: { fontSize: 14, fontWeight: "700", color: "#333" },
  listeBaslikAlt:  { fontSize: 11, color: "#AAA" },

  liste:          { paddingHorizontal: 12, paddingBottom: 24 },
  kart: {
    backgroundColor: "#FFF", borderRadius: 10,
    padding: 12, marginBottom: 8,
    shadowColor: "#000", shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.04, shadowRadius: 3, elevation: 2,
  },
  kartUst:        { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 6 },
  kartSol:        { flexDirection: "row", alignItems: "center", gap: 6, flex: 1 },
  kartSag:        { flexDirection: "row", alignItems: "center", gap: 6 },
  kartIstasyon:   { fontSize: 13, fontWeight: "600", color: "#222", flex: 1 },
  riskBadge:      { borderRadius: 6, paddingHorizontal: 7, paddingVertical: 2 },
  riskText:       { fontSize: 11, fontWeight: "700" },
  simBadge: {
    backgroundColor: "#E3F2FD", borderRadius: 5,
    paddingHorizontal: 5, paddingVertical: 1,
    borderWidth: 1, borderColor: "#BBDEFB",
  },
  simBadgeText:   { fontSize: 9, color: "#0056b3", fontWeight: "800", letterSpacing: 0.5 },
  sensorSatir:    { flexDirection: "row", flexWrap: "wrap", gap: 6, marginBottom: 4 },
  sensor: {
    fontSize: 11, color: "#555",
    backgroundColor: "#F5F5F5", borderRadius: 5,
    paddingHorizontal: 6, paddingVertical: 2,
    fontVariant: ["tabular-nums"],
  },
  kartTarih:      { fontSize: 10, color: "#BBB" },

  yukleniyorBox:  { flex: 1, justifyContent: "center", alignItems: "center", gap: 12 },
  yukleniyorText: { color: "#888", fontSize: 14 },
  bosBox:         { alignItems: "center", paddingTop: 60, gap: 8 },
  bosText:        { fontSize: 16, fontWeight: "600", color: "#888" },
  bosAlt:         { fontSize: 13, color: "#AAA" },
});
