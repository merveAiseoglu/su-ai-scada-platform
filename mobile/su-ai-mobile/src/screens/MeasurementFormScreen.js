// screens/OlcumFormuScreen.js
// Ölçüm Giriş Formu — Saha koşullarına uygun, büyük butonlu hızlı form

import React, { useState } from "react";
import {
  View, Text, StyleSheet, ScrollView, TextInput,
  TouchableOpacity, Alert, ActivityIndicator, KeyboardAvoidingView, Platform,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { MaterialCommunityIcons } from "@expo/vector-icons";
import { postOlcum } from "../services/api";
import { kaydetOlcum } from "../services/offlineStorage";
import { useNetworkStatus } from "../hooks/useNetworkStatus";

const PARAMETRELER = [
  {
    key: "ph",
    label: "pH Değeri",
    ikon: "flask",
    birim: "",
    klavye: "numeric",
    aciklama: "Normal aralık: 6.5 — 8.5",
    renk: "#7C3AED",
  },
  {
    key: "serbest_klor",
    label: "Serbest Klor",
    ikon: "test-tube",
    birim: "mg/L",
    klavye: "numeric",
    aciklama: "Normal aralık: 0.2 — 0.5 mg/L",
    renk: "#059669",
  },
  {
    key: "bulaniklik",
    label: "Bulanıklık",
    ikon: "water-opacity",
    birim: "NTU",
    klavye: "numeric",
    aciklama: "Kabul edilebilir: < 1.0 NTU",
    renk: "#0284C7",
  },
  {
    key: "iletkenlik",
    label: "İletkenlik",
    ikon: "lightning-bolt",
    birim: "µS/cm",
    klavye: "numeric",
    aciklama: "Kabul edilebilir: ≤ 2500",
    renk: "#D97706",
  },
  {
    key: "sicaklik",
    label: "Sıcaklık",
    ikon: "thermometer",
    birim: "°C",
    klavye: "numeric",
    aciklama: "Referans değer: 12 — 25°C",
    renk: "#DC2626",
  },
];

export default function MeasurementFormScreen({ navigation, route }) {
  const { istasyon } = route.params;
  const { isOnline } = useNetworkStatus();

  const [degerler, setDegerler] = useState({
    ph: "", serbest_klor: "", bulaniklik: "", iletkenlik: "", sicaklik: "",
  });
  const [personelNotu, setPersonelNotu] = useState("");
  const [gonderiyor, setGonderiyor] = useState(false);

  const degerGuncelle = (key, value) => {
    // Virgülü noktaya çevir (Türk klavye düzeni)
    const temiz = value.replace(",", ".");
    setDegerler((prev) => ({ ...prev, [key]: temiz }));
  };

  const olcumOlustur = () => ({
    istasyon_id: istasyon.id,
    ph: degerler.ph !== "" ? parseFloat(degerler.ph) : null,
    serbest_klor: degerler.serbest_klor !== "" ? parseFloat(degerler.serbest_klor) : null,
    bulaniklik: degerler.bulaniklik !== "" ? parseFloat(degerler.bulaniklik) : null,
    iletkenlik: degerler.iletkenlik !== "" ? parseFloat(degerler.iletkenlik) : null,
    sicaklik: degerler.sicaklik !== "" ? parseFloat(degerler.sicaklik) : null,
    personel_notu: personelNotu || null,
  });

  const zorunluAlanlarDoluMu = () => {
    return degerler.ph !== "" && degerler.serbest_klor !== "" && degerler.bulaniklik !== "";
  };

  const formGonder = async () => {
    if (!zorunluAlanlarDoluMu()) {
      Alert.alert("Eksik Veri", "Lütfen pH, Serbest Klor ve Bulanıklık değerlerini eksiksiz girin.");
      return;
    }

    setGonderiyor(true);
    const olcumData = olcumOlustur();

    if (!isOnline) {
      // --- OFFLINE YOLU ---
      try {
        const yerelId = await kaydetOlcum(olcumData);
        Alert.alert(
          "📵 Çevrimdışı Kaydedildi",
          "Ölçüm yerel veritabanına kaydedildi. İnternete bağlandığınızda otomatik olarak gönderilecek.",
          [{ text: "Tamam", onPress: () => navigation.goBack() }]
        );
      } catch (err) {
        Alert.alert("Hata", "Yerel kayıt başarısız: " + err.message);
      } finally {
        setGonderiyor(false);
      }
      return;
    }

    // --- ONLINE YOLU ---
    try {
      const yanit = await postOlcum(olcumData);
      navigation.navigate("ResultScreen", {
        olcumId: yanit.id,
        istasyon: istasyon,
        ilkAnalizSonucu: yanit.analiz_sonucu,
      });
    } catch (err) {
      if (err.message === "NETWORK_ERROR") {
        // Bağlantı koptuğunda otomatik offline'a geç
        try {
          await kaydetOlcum(olcumData);
          Alert.alert(
            "⚠️ Bağlantı Kesildi",
            "İnternet bağlantısı kesildi. Ölçüm çevrimdışı kaydedildi.",
            [{ text: "Tamam", onPress: () => navigation.goBack() }]
          );
        } catch (offlineErr) {
          Alert.alert("Kritik Hata", "Gönderim ve yerel kayıt her ikisi de başarısız.");
        }
      } else {
        Alert.alert("Sunucu Hatası", err.message);
      }
    } finally {
      setGonderiyor(false);
    }
  };

  return (
    <SafeAreaView style={styles.kapsayici}>
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : "height"}
        style={{ flex: 1 }}
      >
        {/* Header */}
        <View style={styles.header}>
          <TouchableOpacity style={styles.geriBtn} onPress={() => navigation.goBack()}>
            <Text style={styles.geriBtnText}>‹ Geri</Text>
          </TouchableOpacity>
          <View style={styles.headerOrta}>
            <Text style={styles.headerBaslik}>{istasyon.ad}</Text>
            <Text style={styles.headerAlt}>{istasyon.tip} · {istasyon.konum || "Konum yok"}</Text>
          </View>
          <View style={[styles.offlineBadge, !isOnline && styles.offlineBadgeAktif]}>
            <MaterialCommunityIcons name={isOnline ? "wifi" : "wifi-off"} size={24} color={isOnline ? "#28A745" : "#DC3545"} />
          </View>
        </View>

        <ScrollView
          showsVerticalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
          contentContainerStyle={styles.icerik}
        >
          <Text style={styles.bolumBaslik}>Ölçüm Değerleri</Text>

          {PARAMETRELER.map((param) => (
            <View key={param.key} style={styles.paramKart}>
              <View style={styles.paramHeader}>
                <MaterialCommunityIcons name={param.ikon} size={28} color={param.renk} style={styles.paramIkon} />
                <View style={styles.paramBilgi}>
                  <Text style={styles.paramLabel}>{param.label}</Text>
                  <Text style={styles.paramAciklama}>{param.aciklama}</Text>
                </View>
                {param.birim !== "" && (
                  <View style={[styles.birimBadge, { borderColor: param.renk + "44" }]}>
                    <Text style={[styles.birimText, { color: param.renk }]}>{param.birim}</Text>
                  </View>
                )}
              </View>
              <TextInput
                style={[
                  styles.girdi,
                  degerler[param.key] !== "" && styles.girdiDolu,
                  degerler[param.key] !== "" && { borderColor: param.renk + "88" },
                ]}
                value={degerler[param.key]}
                onChangeText={(v) => degerGuncelle(param.key, v)}
                keyboardType={param.klavye}
                placeholder={`${param.label} girin...`}
                placeholderTextColor="#999"
                returnKeyType="next"
              />
            </View>
          ))}

          {/* Personel Notu */}
          <View style={styles.paramKart}>
            <View style={styles.paramHeader}>
              <MaterialCommunityIcons name="clipboard-text-outline" size={28} color="#666666" style={styles.paramIkon} />
              <View style={styles.paramBilgi}>
                <Text style={styles.paramLabel}>Personel Notu</Text>
                <Text style={styles.paramAciklama}>İsteğe bağlı gözlem notu</Text>
              </View>
            </View>
            <TextInput
              style={[styles.girdi, styles.notGirdisi]}
              value={personelNotu}
              onChangeText={setPersonelNotu}
              placeholder="Saha gözlemlerinizi yazın..."
              placeholderTextColor="#999"
              multiline
              numberOfLines={3}
              textAlignVertical="top"
            />
          </View>

          {/* Gönder Butonu */}
          <TouchableOpacity
            style={[styles.gonderBtn, gonderiyor && styles.gonderBtnDevre, !isOnline && styles.gonderBtnOffline]}
            onPress={formGonder}
            disabled={gonderiyor}
            activeOpacity={0.85}
          >
            {gonderiyor ? (
              <ActivityIndicator color="#FFFFFF" size="small" />
            ) : (
              <>
                <MaterialCommunityIcons name={isOnline ? "cloud-upload" : "content-save"} size={24} color="#FFFFFF" style={styles.gonderBtnIkon} />
                <Text style={styles.gonderBtnText}>
                  {isOnline ? "Analiz Et & Gönder" : "Çevrimdışı Kaydet"}
                </Text>
              </>
            )}
          </TouchableOpacity>

          {!isOnline && (
            <View style={styles.offlineUyari}>
              <MaterialCommunityIcons name="wifi-strength-off-outline" size={24} color="#856404" style={{marginRight: 8}} />
              <Text style={styles.offlineUyariText}>
                Çevrimdışı mod aktif. Ölçüm yerel veritabanına kaydedilecek
                ve internete bağlandığınızda otomatik gönderilecektir.
              </Text>
            </View>
          )}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  kapsayici: { flex: 1, backgroundColor: "#F8F9FA" },
  header: {
    flexDirection: "row", alignItems: "center", paddingHorizontal: 16,
    paddingVertical: 14, borderBottomWidth: 1, borderBottomColor: "rgba(0,0,0,0.05)",
    gap: 12, backgroundColor: "#FFFFFF"
  },
  geriBtn: { padding: 8 },
  geriBtnText: { color: "#0056b3", fontSize: 18, fontWeight: "600" },
  headerOrta: { flex: 1 },
  headerBaslik: { fontSize: 18, fontWeight: "700", color: "#333333" },
  headerAlt: { fontSize: 12, color: "#666666", marginTop: 2 },
  offlineBadge: { padding: 4 },
  offlineBadgeAktif: {},
  offlineBadgeText: { fontSize: 16 },
  icerik: { padding: 16, paddingBottom: 40 },
  bolumBaslik: {
    fontSize: 14, fontWeight: "700", color: "#666666",
    letterSpacing: 1, textTransform: "uppercase", marginBottom: 14,
  },
  paramKart: {
    backgroundColor: "#FFFFFF", borderRadius: 12,
    padding: 16, marginBottom: 16, borderWidth: 1, borderColor: "rgba(0,0,0,0.05)",
    shadowColor: "#000", shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.05, shadowRadius: 4, elevation: 2
  },
  paramHeader: { flexDirection: "row", alignItems: "center", marginBottom: 16, gap: 10 },
  paramIkon: { marginRight: 4 },
  paramBilgi: { flex: 1 },
  paramLabel: { fontSize: 16, fontWeight: "600", color: "#333333" },
  paramAciklama: { fontSize: 12, color: "#666666", marginTop: 2 },
  birimBadge: {
    borderWidth: 1, borderRadius: 8, paddingHorizontal: 8, paddingVertical: 4,
  },
  birimText: { fontSize: 12, fontWeight: "700" },
  girdi: {
    backgroundColor: "#F5F5F5", borderRadius: 12,
    borderWidth: 1, borderColor: "#E0E0E0",
    paddingHorizontal: 16, paddingVertical: 16,
    color: "#333333", fontSize: 18, fontWeight: "600",
  },
  girdiDolu: { backgroundColor: "#FFFFFF" },
  notGirdisi: { fontSize: 16, fontWeight: "400", minHeight: 80, paddingTop: 12 },
  gonderBtn: {
    backgroundColor: "#0056b3", borderRadius: 12,
    paddingVertical: 18, marginTop: 20,
    flexDirection: "row", justifyContent: "center", alignItems: "center", gap: 10,
    shadowColor: "#0056b3", shadowOffset: { width: 0, height: 4 }, shadowOpacity: 0.2, shadowRadius: 8,
    elevation: 4,
  },
  gonderBtnDevre: { opacity: 0.7 },
  gonderBtnOffline: { backgroundColor: "#6c757d" },
  gonderBtnIkon: { fontSize: 20 },
  gonderBtnText: { fontSize: 18, fontWeight: "700", color: "#FFFFFF" },
  offlineUyari: {
    backgroundColor: "#FFF3CD", borderRadius: 12, padding: 14, marginTop: 16,
    borderWidth: 1, borderColor: "#FFEEBA", flexDirection: "row", alignItems: "center",
  },
  offlineUyariText: { color: "#856404", fontSize: 13, lineHeight: 20, flex: 1 },
});
