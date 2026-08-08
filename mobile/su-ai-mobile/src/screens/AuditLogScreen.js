// screens/AuditLogScreen.js
// Faz 2 — Denetim İzi (Audit Trail) Ekranı
// Sadece yönetici rolüne sahip kullanıcıların görebildiği işlem geçmişi.

import React, { useState, useEffect, useCallback } from "react";
import {
  View, Text, FlatList, TouchableOpacity, StyleSheet,
  ActivityIndicator, RefreshControl,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { MaterialCommunityIcons } from "@expo/vector-icons";
import { getAuditLogs } from "../services/api";

const ISLEM_IKONLARI = {
  LOGIN: "login",
  ISTASYON_EKLENDI: "plus-circle-outline",
  OLCUM_EKLENDI: "flask-outline",
  SIM_OLCUM: "lightning-bolt-circle",
};

const ISLEM_RENKLERI = {
  LOGIN: "#0056b3",
  ISTASYON_EKLENDI: "#27AE60",
  OLCUM_EKLENDI: "#8E44AD",
  SIM_OLCUM: "#F39C12",
};

export default function AuditLogScreen({ navigation }) {
  const [logs, setLogs] = useState([]);
  const [yukleniyor, setYukleniyor] = useState(true);
  const [yenileniyor, setYenileniyor] = useState(false);
  const [hata, setHata] = useState(null);

  const veriYukle = useCallback(async (sessiz = false) => {
    if (!sessiz) setYukleniyor(true);
    setHata(null);
    try {
      const data = await getAuditLogs(100);
      setLogs(data);
    } catch (e) {
      if (e.message.includes("403")) {
        setHata("Bu ekranı görüntüleme yetkiniz yok (Sadece Yönetici).");
      } else {
        setHata("Loglar alınırken hata oluştu: " + e.message);
      }
    } finally {
      setYukleniyor(false);
      setYenileniyor(false);
    }
  }, []);

  useEffect(() => {
    veriYukle();
  }, [veriYukle]);

  const renderLog = ({ item }) => {
    const ikon = ISLEM_IKONLARI[item.islem_tipi] || "information-outline";
    const renk = ISLEM_RENKLERI[item.islem_tipi] || "#555";
    const tarih = new Date(item.timestamp).toLocaleString("tr-TR");

    return (
      <View style={styles.kart}>
        <View style={[styles.ikonKutu, { backgroundColor: renk + "15" }]}>
          <MaterialCommunityIcons name={ikon} size={24} color={renk} />
        </View>
        <View style={styles.icerik}>
          <View style={styles.baslikSatir}>
            <Text style={styles.islemTipi}>{item.islem_tipi}</Text>
            <Text style={styles.tarih}>{tarih}</Text>
          </View>
          <Text style={styles.kullanici}>👤 Kullanıcı ID: {item.kullanici_id}</Text>
          {item.detay && <Text style={styles.detay}>{item.detay}</Text>}
        </View>
      </View>
    );
  };

  return (
    <SafeAreaView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity style={styles.backBtn} onPress={() => navigation.goBack()}>
          <MaterialCommunityIcons name="arrow-left" size={24} color="#0056b3" />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={styles.headerBaslik}>Denetim İzi (Audit Log)</Text>
          <Text style={styles.headerAlt}>Sistem işlem geçmişi</Text>
        </View>
        <TouchableOpacity onPress={() => { setYenileniyor(true); veriYukle(); }}>
          <MaterialCommunityIcons name="refresh" size={24} color="#0056b3" />
        </TouchableOpacity>
      </View>

      {/* Liste */}
      {yukleniyor ? (
        <View style={styles.merkezBox}>
          <ActivityIndicator size="large" color="#0056b3" />
          <Text style={styles.mesaj}>Kayıtlar yükleniyor...</Text>
        </View>
      ) : hata ? (
        <View style={styles.merkezBox}>
          <MaterialCommunityIcons name="shield-lock-outline" size={48} color="#E74C3C" />
          <Text style={styles.hataText}>{hata}</Text>
        </View>
      ) : (
        <FlatList
          data={logs}
          keyExtractor={(item) => item.id.toString()}
          renderItem={renderLog}
          contentContainerStyle={styles.liste}
          refreshControl={
            <RefreshControl
              refreshing={yenileniyor}
              onRefresh={() => { setYenileniyor(true); veriYukle(); }}
              tintColor="#0056b3"
            />
          }
          ListEmptyComponent={
            <View style={styles.merkezBox}>
              <MaterialCommunityIcons name="history" size={48} color="#CCC" />
              <Text style={styles.mesaj}>Henüz işlem kaydı yok.</Text>
            </View>
          }
        />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#F8F9FA" },
  header: {
    flexDirection: "row", alignItems: "center",
    paddingHorizontal: 16, paddingVertical: 12,
    backgroundColor: "#FFF",
    borderBottomWidth: 1, borderBottomColor: "rgba(0,0,0,0.07)",
    elevation: 3,
  },
  backBtn:      { padding: 6, marginRight: 10 },
  headerBaslik: { fontSize: 18, fontWeight: "700", color: "#0056b3" },
  headerAlt:    { fontSize: 11, color: "#888", marginTop: 1 },

  liste: { padding: 12, paddingBottom: 24 },
  kart: {
    flexDirection: "row",
    backgroundColor: "#FFF",
    padding: 12,
    borderRadius: 12,
    marginBottom: 8,
    borderWidth: 1, borderColor: "rgba(0,0,0,0.05)",
  },
  ikonKutu: {
    width: 44, height: 44, borderRadius: 22,
    justifyContent: "center", alignItems: "center",
    marginRight: 12,
  },
  icerik: { flex: 1 },
  baslikSatir: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 4 },
  islemTipi: { fontSize: 14, fontWeight: "700", color: "#1A1A2E" },
  tarih: { fontSize: 11, color: "#888" },
  kullanici: { fontSize: 12, color: "#555", marginBottom: 4 },
  detay: { fontSize: 13, color: "#444", fontStyle: "italic", backgroundColor: "#F8F9FA", padding: 6, borderRadius: 6 },

  merkezBox: { flex: 1, justifyContent: "center", alignItems: "center", padding: 24, gap: 12 },
  mesaj: { fontSize: 14, color: "#888", textAlign: "center" },
  hataText: { fontSize: 15, color: "#E74C3C", textAlign: "center", fontWeight: "600" },
});
