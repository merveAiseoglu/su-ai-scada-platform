// screens/GecmisOlcumlerimScreen.js
// Geçmiş Ölçümlerim — Kullanıcının tüm ölçümlerini risk rozetli liste halinde gösterir
import React, { useState, useEffect, useCallback, useMemo } from "react";
import {
  View, Text, FlatList, TouchableOpacity, StyleSheet,
  StatusBar, ActivityIndicator, RefreshControl, ScrollView, Alert,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { MaterialCommunityIcons } from "@expo/vector-icons";
import { getSonOlcumler, getIstasyonlar } from "../services/api";
import { getSenkronizeEdilmemisOlcumler } from "../services/offlineStorage";
import { RISK_KONFIG } from "./ResultScreen";

const FILTRELER = ["TÜMÜ", "NORMAL", "DÜŞÜK", "ORTA", "KRİTİK"];
const SAYFA_BOYUTU = 50;

export default function GecmisOlcumlerimScreen({ navigation }) {
  const [olcumler, setOlcumler] = useState([]);
  const [istasyonMap, setIstasyonMap] = useState({});
  const [yukleniyor, setYukleniyor] = useState(true);
  const [yenileniyor, setYenileniyor] = useState(false);
  const [dahaYukleniyor, setDahaYukleniyor] = useState(false);
  const [dahaFazlaVar, setDahaFazlaVar] = useState(true);
  const [seciliFiltre, setSeciliFiltre] = useState("TÜMÜ");

  const veriYukle = useCallback(async (sifirla = false) => {
    try {
      const [olcumVerisi, istasyonVerisi, yerelVeriler] = await Promise.all([
        getSonOlcumler(SAYFA_BOYUTU, null, 0).catch(() => []),
        getIstasyonlar().catch(() => []),
        getSenkronizeEdilmemisOlcumler().catch(() => []),
      ]);

      const map = {};
      (istasyonVerisi || []).forEach((ist) => { map[ist.id] = ist; });
      setIstasyonMap(map);

      // Yerel SQLite kayıtlarını biçimlendir
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
        personel_notu: y.personel_notu,
        olcum_tarihi: y.olusturulma ? new Date(y.olusturulma.replace(" ", "T")).toISOString() : new Date().toISOString(),
        risk_seviyesi: null,
        analiz_durumu: "YEREL_BEKLIYOR",
      }));

      // Yerel ve sunucu kayıtlarını tarihe göre azalan (en yeni üstte) birleştir
      const sunucuListesi = olcumVerisi || [];
      const birlesik = [...yerelFormatli, ...sunucuListesi];
      birlesik.sort((a, b) => new Date(b.olcum_tarihi) - new Date(a.olcum_tarihi));

      setOlcumler(birlesik);
      setDahaFazlaVar(sunucuListesi.length === SAYFA_BOYUTU);
    } catch (err) {
      console.error("Geçmiş ölçümler yüklenemedi", err);
    } finally {
      setYukleniyor(false);
      setYenileniyor(false);
    }
  }, []);

  useEffect(() => { veriYukle(); }, [veriYukle]);

  const yenile = () => {
    setYenileniyor(true);
    veriYukle(true);
  };

  const dahaFazlaYukle = async () => {
    if (dahaYukleniyor || !dahaFazlaVar || yukleniyor || yenileniyor) return;
    try {
      setDahaYukleniyor(true);
      // Sadece sunucu kayıtlarının sayısına göre offset hesapla
      const sunucuKayitSayisi = olcumler.filter((o) => !o._isLocal).length;
      const yeniVeri = await getSonOlcumler(SAYFA_BOYUTU, null, sunucuKayitSayisi);
      if (yeniVeri.length < SAYFA_BOYUTU) {
        setDahaFazlaVar(false);
      }
      if (yeniVeri.length > 0) {
        setOlcumler((prev) => {
          const yereller = prev.filter((o) => o._isLocal);
          const mevcutSunucu = prev.filter((o) => !o._isLocal);
          const birlesikSunucu = [...mevcutSunucu, ...yeniVeri];
          const tumu = [...yereller, ...birlesikSunucu];
          tumu.sort((a, b) => new Date(b.olcum_tarihi) - new Date(a.olcum_tarihi));
          return tumu;
        });
      }
    } catch (err) {
      console.error("Daha fazla ölçüm yüklenirken hata:", err);
    } finally {
      setDahaYukleniyor(false);
    }
  };

  const filtrelenmisOlcumler = useMemo(() => {
    if (seciliFiltre === "TÜMÜ") return olcumler;
    return olcumler.filter((item) => !item._isLocal && item.risk_seviyesi === seciliFiltre);
  }, [olcumler, seciliFiltre]);

  const tarihFormatla = (tarihStr) => {
    const d = new Date(tarihStr);
    return d.toLocaleDateString("tr-TR", { day: "2-digit", month: "short", year: "numeric" }) +
      " · " + d.toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" });
  };

  const renderItem = ({ item }) => {
    const konfig = RISK_KONFIG[item.risk_seviyesi] || RISK_KONFIG.NORMAL;
    const istasyon = istasyonMap[item.istasyon_id];

    return (
      <TouchableOpacity
        style={[styles.kart, item._isLocal && styles.yerelKart]}
        activeOpacity={0.8}
        onPress={() => {
          if (item._isLocal) {
            Alert.alert(
              "📵 Çevrimdışı Kayıt",
              "Bu ölçüm henüz sunucuya iletilmediği için yapay zeka analizi ve detay raporu üretilmemiştir. İnternet bağlantısı sağlandığında otomatik gönderilecektir."
            );
            return;
          }
          navigation.navigate("ResultScreen", {
            olcumId: item.id,
            istasyon: istasyon || { id: item.istasyon_id, ad: "Bilinmeyen İstasyon" },
          });
        }}
      >
        <View style={styles.kartUst}>
          <Text style={styles.istasyonAdi} numberOfLines={1}>
            {istasyon?.ad || `İstasyon #${item.istasyon_id}`}
          </Text>

          {item._isLocal ? (
            <View
              style={[
                styles.riskRozet,
                styles.yerelRozet,
                item._durum === "gonderiliyor" && styles.gonderiliyorRozet,
                item._durum === "hata" && styles.hataRozet,
              ]}
            >
              <MaterialCommunityIcons
                name={
                  item._durum === "gonderiliyor"
                    ? "cloud-sync"
                    : item._durum === "hata"
                    ? "alert-circle-outline"
                    : "cloud-upload-outline"
                }
                size={13}
                color={
                  item._durum === "gonderiliyor"
                    ? "#2B6CB0"
                    : item._durum === "hata"
                    ? "#C53030"
                    : "#D97706"
                }
                style={{ marginRight: 4 }}
              />
              <Text
                style={[
                  styles.riskRozetText,
                  {
                    color:
                      item._durum === "gonderiliyor"
                        ? "#2B6CB0"
                        : item._durum === "hata"
                        ? "#C53030"
                        : "#D97706",
                  },
                ]}
              >
                {item._durum === "gonderiliyor"
                  ? "Gönderiliyor..."
                  : item._durum === "hata"
                  ? "Tekrar Denenecek"
                  : "Senkronizasyon Bekliyor"}
              </Text>
            </View>
          ) : (
            <View style={[styles.riskRozet, { backgroundColor: konfig.arkaplan, borderColor: konfig.kenar }]}>
              <MaterialCommunityIcons name={konfig.ikon} size={14} color={konfig.renk} style={{ marginRight: 4 }} />
              <Text style={[styles.riskRozetText, { color: konfig.renk }]}>{konfig.etiket}</Text>
            </View>
          )}
        </View>
        <Text style={styles.tarih}>{tarihFormatla(item.olcum_tarihi)}</Text>
        <View style={styles.olcumSatiri}>
          {item.ph != null && (
            <View style={styles.olcumPill}>
              <MaterialCommunityIcons name="water-outline" size={12} color="#007AFF" style={styles.paramIkon} />
              <Text style={styles.olcumDeger}>pH: {item.ph}</Text>
            </View>
          )}
          {item.serbest_klor != null && (
            <View style={styles.olcumPill}>
              <MaterialCommunityIcons name="flask-outline" size={12} color="#28A745" style={styles.paramIkon} />
              <Text style={styles.olcumDeger}>Klor: {item.serbest_klor} mg/L</Text>
            </View>
          )}
          {item.bulaniklik != null && (
            <View style={styles.olcumPill}>
              <MaterialCommunityIcons name="blur" size={12} color="#FF9500" style={styles.paramIkon} />
              <Text style={styles.olcumDeger}>Bulanıklık: {item.bulaniklik} NTU</Text>
            </View>
          )}
          {item.iletkenlik != null && (
            <View style={styles.olcumPill}>
              <MaterialCommunityIcons name="flash-outline" size={12} color="#5856D6" style={styles.paramIkon} />
              <Text style={styles.olcumDeger}>İletkenlik: {item.iletkenlik} µS/cm</Text>
            </View>
          )}
          {item.sicaklik != null && (
            <View style={styles.olcumPill}>
              <MaterialCommunityIcons name="thermometer" size={12} color="#FF3B30" style={styles.paramIkon} />
              <Text style={styles.olcumDeger}>Sıcaklık: {item.sicaklik} °C</Text>
            </View>
          )}
        </View>
      </TouchableOpacity>
    );
  };

  const renderFooter = () => {
    if (!dahaYukleniyor) return null;
    return (
      <View style={styles.footerYukleniyor}>
        <ActivityIndicator size="small" color="#0056b3" />
        <Text style={styles.footerYukleniyorText}>Daha fazla ölçüm yükleniyor...</Text>
      </View>
    );
  };

  if (yukleniyor) {
    return (
      <SafeAreaView style={styles.container}>
        <StatusBar barStyle="dark-content" />
        <View style={styles.baslikSatiri}>
          <TouchableOpacity onPress={() => navigation.goBack()}>
            <MaterialCommunityIcons name="arrow-left" size={24} color="#0056b3" />
          </TouchableOpacity>
          <Text style={styles.baslik}>Geçmiş Ölçümlerim</Text>
          <View style={{ width: 24 }} />
        </View>
        <View style={styles.yukleniyorKapsayici}>
          <ActivityIndicator size="large" color="#0056b3" />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar barStyle="dark-content" />
      <View style={styles.baslikSatiri}>
        <TouchableOpacity onPress={() => navigation.goBack()}>
          <MaterialCommunityIcons name="arrow-left" size={24} color="#0056b3" />
        </TouchableOpacity>
        <Text style={styles.baslik}>Geçmiş Ölçümlerim</Text>
        <View style={{ width: 24 }} />
      </View>

      {/* Filtre Butonları (Chips / Tabs) */}
      <View style={styles.filtreKapsayici}>
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.filtreListesi}
        >
          {FILTRELER.map((filtre) => {
            const aktif = seciliFiltre === filtre;
            const konfig = RISK_KONFIG[filtre];
            const chipRenk = aktif
              ? (konfig ? konfig.renk : "#0056b3")
              : "#666666";
            const chipBg = aktif
              ? (konfig ? konfig.arkaplan : "rgba(0,86,179,0.12)")
              : "#FFFFFF";
            const chipBorder = aktif
              ? (konfig ? konfig.kenar : "rgba(0,86,179,0.3)")
              : "rgba(0,0,0,0.08)";

            return (
              <TouchableOpacity
                key={filtre}
                style={[
                  styles.chip,
                  { backgroundColor: chipBg, borderColor: chipBorder },
                ]}
                onPress={() => setSeciliFiltre(filtre)}
                activeOpacity={0.7}
              >
                {konfig && (
                  <MaterialCommunityIcons
                    name={konfig.ikon}
                    size={13}
                    color={chipRenk}
                    style={{ marginRight: 4 }}
                  />
                )}
                <Text style={[styles.chipText, { color: chipRenk, fontWeight: aktif ? "700" : "500" }]}>
                  {filtre === "TÜMÜ" ? "Tümü" : (konfig?.etiket || filtre)}
                </Text>
              </TouchableOpacity>
            );
          })}
        </ScrollView>
      </View>

      <FlatList
        data={filtrelenmisOlcumler}
        keyExtractor={(item) => item.id.toString()}
        renderItem={renderItem}
        contentContainerStyle={styles.liste}
        refreshControl={<RefreshControl refreshing={yenileniyor} onRefresh={yenile} />}
        onEndReached={dahaFazlaYukle}
        onEndReachedThreshold={0.3}
        ListFooterComponent={renderFooter}
        ListEmptyComponent={
          <View style={styles.bosKapsayici}>
            <MaterialCommunityIcons name="clipboard-text-off-outline" size={48} color="#CCCCCC" />
            <Text style={styles.bosText}>
              {seciliFiltre === "TÜMÜ"
                ? "Henüz ölçüm kaydı yok."
                : `"${seciliFiltre}" seviyesinde ölçüm kaydı bulunamadı.`}
            </Text>
          </View>
        }
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#F5F5F5" },
  baslikSatiri: {
    flexDirection: "row", alignItems: "center", justifyContent: "space-between",
    paddingHorizontal: 16, paddingVertical: 12, backgroundColor: "#FFFFFF",
    borderBottomWidth: 1, borderBottomColor: "rgba(0,0,0,0.05)",
  },
  baslik: { fontSize: 17, fontWeight: "700", color: "#1A1A1A" },
  yukleniyorKapsayici: { flex: 1, justifyContent: "center", alignItems: "center" },
  filtreKapsayici: {
    backgroundColor: "#FFFFFF",
    borderBottomWidth: 1,
    borderBottomColor: "rgba(0,0,0,0.05)",
    paddingVertical: 8,
  },
  filtreListesi: {
    paddingHorizontal: 12,
    flexDirection: "row",
    gap: 8,
  },
  chip: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 20,
    borderWidth: 1,
  },
  chipText: {
    fontSize: 12,
  },
  liste: { padding: 12, flexGrow: 1 },
  kart: {
    backgroundColor: "#FFFFFF", borderRadius: 12, padding: 14, marginBottom: 10,
    borderWidth: 1, borderColor: "rgba(0,0,0,0.05)",
    shadowColor: "#000", shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.04, shadowRadius: 2, elevation: 1,
  },
  yerelKart: {
    borderColor: "rgba(217, 119, 6, 0.25)",
    backgroundColor: "#FFFCF5",
  },
  kartUst: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 4 },
  istasyonAdi: { fontSize: 15, fontWeight: "700", color: "#1A1A1A", flex: 1, marginRight: 8 },
  riskRozet: {
    flexDirection: "row", alignItems: "center", paddingHorizontal: 8, paddingVertical: 4,
    borderRadius: 20, borderWidth: 1,
  },
  yerelRozet: {
    backgroundColor: "#FFFBEB",
    borderColor: "#FDE68A",
  },
  gonderiliyorRozet: {
    backgroundColor: "#EBF5FF",
    borderColor: "#BEE3F8",
  },
  hataRozet: {
    backgroundColor: "#FFF5F5",
    borderColor: "#FEB2B2",
  },
  riskRozetText: { fontSize: 11, fontWeight: "700" },
  tarih: { fontSize: 12, color: "#888888", marginBottom: 8 },
  olcumSatiri: { flexDirection: "row", flexWrap: "wrap", gap: 6 },
  olcumPill: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "rgba(0,0,0,0.03)",
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
  },
  paramIkon: { marginRight: 4 },
  olcumDeger: { fontSize: 11.5, color: "#444444", fontWeight: "600" },
  footerYukleniyor: {
    flexDirection: "row",
    justifyContent: "center",
    alignItems: "center",
    paddingVertical: 14,
    gap: 8,
  },
  footerYukleniyorText: {
    fontSize: 12,
    color: "#666666",
  },
  bosKapsayici: { flex: 1, justifyContent: "center", alignItems: "center", paddingTop: 80 },
  bosText: { fontSize: 14, color: "#999999", marginTop: 12 },
});
