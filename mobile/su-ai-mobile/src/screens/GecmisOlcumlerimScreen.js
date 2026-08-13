// screens/GecmisOlcumlerimScreen.js
// Geçmiş Ölçümlerim — Kullanıcının tüm ölçümlerini risk rozetli liste halinde gösterir
import React, { useState, useEffect, useCallback } from "react";
import {
  View, Text, FlatList, TouchableOpacity, StyleSheet,
  StatusBar, ActivityIndicator, RefreshControl,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { MaterialCommunityIcons } from "@expo/vector-icons";
import { getSonOlcumler, getIstasyonlar } from "../services/api";
import { RISK_KONFIG } from "./ResultScreen";

export default function GecmisOlcumlerimScreen({ navigation }) {
  const [olcumler, setOlcumler] = useState([]);
  const [istasyonMap, setIstasyonMap] = useState({});
  const [yukleniyor, setYukleniyor] = useState(true);
  const [yenileniyor, setYenileniyor] = useState(false);

  const veriYukle = useCallback(async () => {
    try {
      const [olcumVerisi, istasyonVerisi] = await Promise.all([
        getSonOlcumler(50),
        getIstasyonlar(),
      ]);
      const map = {};
      istasyonVerisi.forEach((ist) => { map[ist.id] = ist; });
      setIstasyonMap(map);
      setOlcumler(olcumVerisi);
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
    veriYukle();
  };

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
        style={styles.kart}
        activeOpacity={0.8}
        onPress={() => navigation.navigate("ResultScreen", {
          olcumId: item.id,
          istasyon: istasyon || { id: item.istasyon_id, ad: "Bilinmeyen İstasyon" },
        })}
      >
        <View style={styles.kartUst}>
          <Text style={styles.istasyonAdi} numberOfLines={1}>
            {istasyon?.ad || `İstasyon #${item.istasyon_id}`}
          </Text>
          <View style={[styles.riskRozet, { backgroundColor: konfig.arkaplan, borderColor: konfig.kenar }]}>
            <MaterialCommunityIcons name={konfig.ikon} size={14} color={konfig.renk} style={{ marginRight: 4 }} />
            <Text style={[styles.riskRozetText, { color: konfig.renk }]}>{konfig.etiket}</Text>
          </View>
        </View>
        <Text style={styles.tarih}>{tarihFormatla(item.olcum_tarihi)}</Text>
        <View style={styles.olcumSatiri}>
          {item.ph != null && <Text style={styles.olcumDeger}>pH: {item.ph}</Text>}
          {item.serbest_klor != null && <Text style={styles.olcumDeger}>Klor: {item.serbest_klor} mg/L</Text>}
          {item.bulaniklik != null && <Text style={styles.olcumDeger}>Bulanıklık: {item.bulaniklik} NTU</Text>}
        </View>
      </TouchableOpacity>
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
      <FlatList
        data={olcumler}
        keyExtractor={(item) => item.id.toString()}
        renderItem={renderItem}
        contentContainerStyle={styles.liste}
        refreshControl={<RefreshControl refreshing={yenileniyor} onRefresh={yenile} />}
        ListEmptyComponent={
          <View style={styles.bosKapsayici}>
            <MaterialCommunityIcons name="clipboard-text-off-outline" size={48} color="#CCCCCC" />
            <Text style={styles.bosText}>Henüz ölçüm kaydı yok.</Text>
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
  liste: { padding: 12, flexGrow: 1 },
  kart: {
    backgroundColor: "#FFFFFF", borderRadius: 12, padding: 14, marginBottom: 10,
    borderWidth: 1, borderColor: "rgba(0,0,0,0.05)",
    shadowColor: "#000", shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.04, shadowRadius: 2, elevation: 1,
  },
  kartUst: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 4 },
  istasyonAdi: { fontSize: 15, fontWeight: "700", color: "#1A1A1A", flex: 1, marginRight: 8 },
  riskRozet: {
    flexDirection: "row", alignItems: "center", paddingHorizontal: 8, paddingVertical: 4,
    borderRadius: 20, borderWidth: 1,
  },
  riskRozetText: { fontSize: 11, fontWeight: "700" },
  tarih: { fontSize: 12, color: "#888888", marginBottom: 8 },
  olcumSatiri: { flexDirection: "row", flexWrap: "wrap", gap: 10 },
  olcumDeger: { fontSize: 12, color: "#555555", fontWeight: "600" },
  bosKapsayici: { flex: 1, justifyContent: "center", alignItems: "center", paddingTop: 80 },
  bosText: { fontSize: 14, color: "#999999", marginTop: 12 },
});
