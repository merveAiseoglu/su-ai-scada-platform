// screens/IstasyonListesiScreen.js
// İstasyon Seçim Ekranı — API'den istasyonları çeken liste

import React, { useState, useEffect, useCallback } from "react";
import {
  View, Text, FlatList, TouchableOpacity, StyleSheet,
  StatusBar, ActivityIndicator, RefreshControl, Alert,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { MaterialCommunityIcons } from "@expo/vector-icons";
import { getIstasyonlar, getUserInfo, logout } from "../services/api";
import { getBekleyenSayisi } from "../services/offlineStorage";
import { useNetworkStatus } from "../hooks/useNetworkStatus";
import { AuthContext } from "../../App";

const TIP_IKONLARI = {
  Kuyu: "water-pump",
  Depo: "water-boiler",
  Şebeke: "pipe-valve",
};

export default function IstasyonListesiScreen({ navigation }) {
  const [istasyonlar, setIstasyonlar] = useState([]);
  const [yukleniyor, setYukleniyor] = useState(true);
  const [yenileniyor, setYenileniyor] = useState(false);
  const [bekleyenSayisi, setBekleyenSayisi] = useState(0);
  const [userInfo, setUserInfo] = useState(null);
  const { isOnline, syncDurumu, manuelSync } = useNetworkStatus();

  const istasyonlarYukle = useCallback(async () => {
    try {
      const veri = await getIstasyonlar();
      setIstasyonlar(veri);
    } catch (err) {
      if (err.message !== "NETWORK_ERROR") {
        Alert.alert("Hata", "İstasyonlar yüklenemedi: " + err.message);
      }
    } finally {
      setYukleniyor(false);
      setYenileniyor(false);
    }
  }, []);

  const bekleyenYukle = useCallback(async () => {
    const sayi = await getBekleyenSayisi();
    setBekleyenSayisi(sayi);
  }, []);

  const userYukle = useCallback(async () => {
    const info = await getUserInfo();
    setUserInfo(info);
  }, []);

  useEffect(() => {
    istasyonlarYukle();
    bekleyenYukle();
    userYukle();
  }, []);

  useEffect(() => {
    bekleyenYukle();
  }, [syncDurumu]);

  const onYenile = () => {
    setYenileniyor(true);
    istasyonlarYukle();
    bekleyenYukle();
  };

  const { setIsLoggedIn } = React.useContext(AuthContext);

  const handleLogout = async () => {
    await logout();
    setIsLoggedIn(false);
  };

  const onSyncBasin = async () => {
    if (!isOnline) {
      Alert.alert("Çevrimdışı", "Senkronizasyon için internet bağlantısı gereklidir.");
      return;
    }
    const sonuc = await manuelSync();
    if (sonuc) {
      Alert.alert(
        "Senkronizasyon Tamamlandı",
        `✅ ${sonuc.basarili} gönderildi\n❌ ${sonuc.basarisiz} hata\n⚠️ ${sonuc.kritik} kritik`
      );
      bekleyenYukle();
    }
  };

  const renderIstasyon = ({ item }) => (
    <TouchableOpacity
      style={[styles.kart, !item.aktif_mi && styles.kartPasif]}
      onPress={() => item.aktif_mi && navigation.navigate("MeasurementForm", { istasyon: item })}
      activeOpacity={0.8}
    >
      <View style={styles.kartSol}>
        <MaterialCommunityIcons 
          name={TIP_IKONLARI[item.tip] || "map-marker"} 
          size={32} 
          color={item.aktif_mi ? "#0056b3" : "#666666"} 
          style={styles.istasyonIkon} 
        />
        <View style={styles.kartBilgi}>
          <Text style={styles.istasyonAd}>{item.ad}</Text>
          <Text style={styles.istasyonKonum}>{item.konum || "Konum girilmemiş"}</Text>
          <View style={styles.tipBadge}>
            <Text style={styles.tipText}>{item.tip}</Text>
          </View>
        </View>
      </View>
      {item.aktif_mi ? (
        <MaterialCommunityIcons name="chevron-right" size={28} color="#0056b3" style={styles.okIcon} />
      ) : (
        <View style={styles.pasifBadge}><Text style={styles.pasifText}>Pasif</Text></View>
      )}
    </TouchableOpacity>
  );

  return (
    <SafeAreaView style={styles.kapsayici}>
      <StatusBar barStyle="light-content" backgroundColor="#0A1628" />

      {/* Header */}
      <View style={styles.header}>
        <View>
          <Text style={styles.headerBaslik}>Su-AI</Text>
          <View style={{ flexDirection: "row", alignItems: "center", marginTop: 2 }}>
            <Text style={styles.headerAlt}>Şanlıurfa Su İşleri</Text>
            {userInfo && (
              <View style={[styles.rolBadge, { backgroundColor: userInfo.rol === "yonetici" ? "#F39C12" : "#27AE60" }]}>
                <Text style={styles.rolText}>{userInfo.rol === "yonetici" ? "YÖNETİCİ" : "SAHA PERSONELİ"}</Text>
              </View>
            )}
          </View>
        </View>
        <View style={styles.headerSag}>
          <TouchableOpacity style={styles.logoutBtn} onPress={handleLogout}>
            <MaterialCommunityIcons name="logout" size={18} color="#E74C3C" />
          </TouchableOpacity>
          <View style={[styles.durum, isOnline ? styles.durumOnline : styles.durumOffline]}>
            <Text style={styles.durumText}>{isOnline ? "● Çevrimiçi" : "● Çevrimdışı"}</Text>
          </View>
          {bekleyenSayisi > 0 && (
            <TouchableOpacity style={styles.syncBtn} onPress={onSyncBasin}>
              <Text style={styles.syncBtnText}>⇄ {bekleyenSayisi}</Text>
            </TouchableOpacity>
          )}
        </View>
      </View>

      {/* Başlık */}
        <View style={styles.araBaslik}>
        <View>
          <Text style={styles.araBaslikText}>İstasyon Seç</Text>
          <Text style={styles.araBaslikAlt}>{istasyonlar.length} istasyon</Text>
        </View>
        <View style={{ flexDirection: "row", gap: 8 }}>
          <TouchableOpacity style={styles.mapBtn} onPress={() => navigation.navigate("MapScreen")}>
            <MaterialCommunityIcons name="map-marker-radius" size={20} color="#FFFFFF" />
            <Text style={styles.mapBtnText}>Harita</Text>
          </TouchableOpacity>
          {userInfo?.rol === "yonetici" && (
            <>
              <TouchableOpacity
                style={[styles.mapBtn, { backgroundColor: "#7B2D8B", paddingHorizontal: 10 }]}
                onPress={() => navigation.navigate("SimulatorScreen")}
              >
                <MaterialCommunityIcons name="lightning-bolt" size={20} color="#FFFFFF" />
                <Text style={styles.mapBtnText}>Sensör Test</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.mapBtn, { backgroundColor: "#34495E", paddingHorizontal: 10 }]}
                onPress={() => navigation.navigate("AuditLogScreen")}
              >
                <MaterialCommunityIcons name="shield-account" size={20} color="#FFFFFF" />
                <Text style={styles.mapBtnText}>Loglar</Text>
              </TouchableOpacity>
            </>
          )}
        </View>
      </View>

      {/* Liste */}
      {yukleniyor ? (
        <View style={styles.yukleniyorContainer}>
          <ActivityIndicator size="large" color="#00D4FF" />
          <Text style={styles.yukleniyorText}>İstasyonlar yükleniyor...</Text>
        </View>
      ) : (
        <FlatList
          data={istasyonlar}
          renderItem={renderIstasyon}
          keyExtractor={(item) => item.id.toString()}
          contentContainerStyle={styles.liste}
          showsVerticalScrollIndicator={false}
          refreshControl={
            <RefreshControl
              refreshing={yenileniyor}
              onRefresh={onYenile}
              tintColor="#00D4FF"
            />
          }
          ListEmptyComponent={
            <View style={styles.bosContainer}>
              <MaterialCommunityIcons name="factory" size={48} color="#999999" style={styles.bosIkon} />
              <Text style={styles.bosText}>İstasyon bulunamadı</Text>
              <Text style={styles.bosAlt}>API bağlantısını kontrol edin</Text>
            </View>
          }
        />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  kapsayici: { flex: 1, backgroundColor: "#F8F9FA" },
  header: {
    flexDirection: "row", justifyContent: "space-between", alignItems: "center",
    paddingHorizontal: 20, paddingVertical: 16,
    borderBottomWidth: 1, borderBottomColor: "rgba(0,0,0,0.05)",
    backgroundColor: "#FFFFFF"
  },
  headerBaslik: { fontSize: 26, fontWeight: "800", color: "#0056b3", letterSpacing: 1 },
  headerAlt: { fontSize: 12, color: "#666666", marginTop: 2 },
  rolBadge: { marginLeft: 8, paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4 },
  rolText: { fontSize: 9, color: "#FFF", fontWeight: "bold" },
  headerSag: { alignItems: "flex-end", gap: 6 },
  logoutBtn: { padding: 4 },
  durum: { paddingHorizontal: 12, paddingVertical: 4, borderRadius: 20 },
  durumOnline: { backgroundColor: "#E8F5E9" },
  durumOffline: { backgroundColor: "#FFEBEE" },
  durumText: { fontSize: 12, fontWeight: "600", color: "#28A745" },
  syncBtn: {
    backgroundColor: "#E3F2FD", paddingHorizontal: 12,
    paddingVertical: 5, borderRadius: 16, borderWidth: 1, borderColor: "#BBDEFB",
  },
  syncBtnText: { color: "#0056b3", fontSize: 13, fontWeight: "700" },
  araBaslik: {
    flexDirection: "row", justifyContent: "space-between", alignItems: "center",
    paddingHorizontal: 20, paddingTop: 20, paddingBottom: 10,
  },
  araBaslikText: { fontSize: 18, fontWeight: "700", color: "#333333" },
  araBaslikAlt: { fontSize: 14, color: "#666666" },
  mapBtn: {
    backgroundColor: "#0056b3", paddingHorizontal: 12, paddingVertical: 8,
    borderRadius: 8, flexDirection: "row", alignItems: "center", gap: 6
  },
  mapBtnText: { color: "#FFFFFF", fontWeight: "700", fontSize: 13 },
  liste: { paddingHorizontal: 16, paddingBottom: 24 },
  kart: {
    backgroundColor: "#FFFFFF", borderRadius: 12,
    padding: 18, marginBottom: 12, flexDirection: "row",
    justifyContent: "space-between", alignItems: "center",
    borderWidth: 1, borderColor: "rgba(0,0,0,0.05)",
    shadowColor: "#000", shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.05, shadowRadius: 4, elevation: 2
  },
  kartPasif: { opacity: 0.5, backgroundColor: "#F5F5F5" },
  kartSol: { flexDirection: "row", alignItems: "center", flex: 1 },
  kartBilgi: { marginLeft: 14, flex: 1 },
  istasyonIkon: { marginRight: 4 },
  istasyonAd: { fontSize: 18, fontWeight: "700", color: "#333333", marginBottom: 4 },
  istasyonKonum: { fontSize: 13, color: "#666666", marginBottom: 6 },
  tipBadge: {
    backgroundColor: "#E3F2FD", borderRadius: 8,
    paddingHorizontal: 8, paddingVertical: 3, alignSelf: "flex-start",
    borderWidth: 1, borderColor: "#BBDEFB",
  },
  tipText: { fontSize: 12, color: "#0056b3", fontWeight: "700" },
  okIcon: { },
  pasifBadge: { backgroundColor: "#E0E0E0", borderRadius: 8, padding: 6 },
  pasifText: { fontSize: 12, color: "#666666", fontWeight: "600" },
  yukleniyorContainer: { flex: 1, justifyContent: "center", alignItems: "center", gap: 16 },
  yukleniyorText: { color: "#666666", fontSize: 16 },
  bosContainer: { flex: 1, justifyContent: "center", alignItems: "center", paddingTop: 60, gap: 8 },
  bosIkon: { marginBottom: 8 },
  bosText: { fontSize: 18, fontWeight: "600", color: "#333333" },
  bosAlt: { fontSize: 14, color: "#666666" },
});
