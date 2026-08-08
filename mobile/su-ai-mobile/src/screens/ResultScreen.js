// screens/SonucScreen.js
// Sonuç Ekranı — Async polling + Skeleton UI + Renk kodlu rozet + LLM Öneri Kartı
//
// Akış:
//   1. Ekran açılır → analiz_durumu "BEKLİYOR" → Skeleton/Spinner gösterilir
//   2. Her 3 saniyede GET /olcumler/{id} poll edilir
//   3. analiz_durumu "TAMAMLANDI" → polling durur, sonuç animasyonlu gösterilir
//   4. analiz_durumu "HATA" → hata ekranı gösterilir

import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  View, Text, StyleSheet, ScrollView,
  TouchableOpacity, Animated, Easing,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { MaterialCommunityIcons } from "@expo/vector-icons";
import { getOlcum } from "../services/api";
import RenkRozeti from "../components/RenkRozeti";

// ---------------------------------------------------------------------------
// Sabitler
// ---------------------------------------------------------------------------

const POLLING_INTERVAL_MS = 3000;   // 3 saniyede bir kontrol
const POLLING_MAX_DENEME  = 60;     // Maksimum 60 deneme (~3 dakika), sonra HATA kabul

const RISK_KONFIG = {
  NORMAL:   { renk: "#00D453", arkaplan: "rgba(0,212,83,0.12)",   kenar: "rgba(0,212,83,0.3)",   ikon: "check-circle", etiket: "NORMAL",      aciklama: "Tüm parametreler kabul edilebilir sınırlar içinde." },
  "DÜŞÜK":  { renk: "#FFD60A", arkaplan: "rgba(255,214,10,0.12)", kenar: "rgba(255,214,10,0.3)", ikon: "alert-circle-outline", etiket: "DÜŞÜK RİSK",  aciklama: "Yakın takip önerilir." },
  ORTA:     { renk: "#FF9F0A", arkaplan: "rgba(255,159,10,0.12)", kenar: "rgba(255,159,10,0.3)", ikon: "alert", etiket: "ORTA RİSK",   aciklama: "Önlem alınması gerekebilir." },
  "KRİTİK": { renk: "#FF3B30", arkaplan: "rgba(255,59,48,0.12)",  kenar: "rgba(255,59,48,0.4)",  ikon: "alert-octagon", etiket: "KRİTİK",      aciklama: "ACİL müdahale gerekli!" },
};

// ---------------------------------------------------------------------------
// Skeleton Parça Bileşeni
// ---------------------------------------------------------------------------

function SkeletonBox({ w, h, style }) {
  const shimmer = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.loop(
      Animated.sequence([
        Animated.timing(shimmer, { toValue: 1, duration: 900, useNativeDriver: true, easing: Easing.inOut(Easing.ease) }),
        Animated.timing(shimmer, { toValue: 0, duration: 900, useNativeDriver: true, easing: Easing.inOut(Easing.ease) }),
      ])
    ).start();
  }, []);

  const opacity = shimmer.interpolate({ inputRange: [0, 1], outputRange: [0.3, 0.7] });

  return (
    <Animated.View
      style={[{ width: w, height: h, borderRadius: 10, backgroundColor: "rgba(255,255,255,0.12)" }, { opacity }, style]}
    />
  );
}

// ---------------------------------------------------------------------------
// AI Güvenilirlik Puanı Kartı (LLM-as-a-Judge)
// ---------------------------------------------------------------------------

function GuvenilirlikPuaniKarti({ metrikler }) {
  const { uyum_puani, gerekce } = metrikler;
  const [gerekceAcik, setGerekceAcik] = useState(false);
  const barAnim = useRef(new Animated.Value(0)).current;

  const yuksekGuven   = uyum_puani >= 70;
  const puanRenk      = yuksekGuven ? "#00D453" : "#FF3B30";
  const puanArkaplan  = yuksekGuven ? "rgba(0,212,83,0.1)"   : "rgba(255,59,48,0.1)";
  const puanKenar     = yuksekGuven ? "rgba(0,212,83,0.25)"  : "rgba(255,59,48,0.25)";

  useEffect(() => {
    Animated.timing(barAnim, {
      toValue: uyum_puani / 100,
      duration: 800,
      useNativeDriver: false,
      easing: Easing.out(Easing.cubic),
    }).start();
  }, [uyum_puani]);

  const barGenislik = barAnim.interpolate({
    inputRange: [0, 1],
    outputRange: ["0%", "100%"],
  });

  return (
    <View style={[styles.guvenBolum, { backgroundColor: puanArkaplan, borderColor: puanKenar }]}>
      {/* Başlık ve rozet */}
      <View style={styles.guvenBaslikSatir}>
        <Text style={styles.guvenBaslik}>AI Güvenilirlik Puanı</Text>
        <View style={[styles.guvenRozetBadge, { backgroundColor: yuksekGuven ? "rgba(0,212,83,0.2)" : "rgba(255,59,48,0.2)", borderColor: puanRenk + "55", flexDirection: 'row', alignItems: 'center' }]}>
          <MaterialCommunityIcons name={yuksekGuven ? "check-circle" : "alert-circle"} size={14} color={puanRenk} style={{marginRight: 4}} />
          <Text style={[styles.guvenRozetText, { color: puanRenk }]}>
            {yuksekGuven ? "Doğrulanmış Öneri" : "İnsan Onayı Bekliyor"}
          </Text>
        </View>
      </View>

      {/* Düşük güven uyarısı */}
      {!yuksekGuven && (
        <View style={styles.guvenUyariKutusu}>
          <MaterialCommunityIcons name="alert-circle" size={16} color="#DC3545" style={{marginTop: 2, marginRight: 6}} />
          <Text style={styles.guvenUyariText}>
            Düşük Güvenilirlik: Bu öneri insan uzman tarafından doğrulanmalıdır.
          </Text>
        </View>
      )}

      {/* Puan + Progress Bar */}
      <View style={styles.guvenPuanSatir}>
        <Text style={[styles.guvenPuan, { color: puanRenk }]}>{uyum_puani}</Text>
        <Text style={styles.guvenPuanBirim}>/100</Text>
        <View style={styles.guvenBarKapsayici}>
          <Animated.View
            style={[styles.guvenBar, { width: barGenislik, backgroundColor: puanRenk }]}
          />
        </View>
      </View>

      {/* Gerekçe — Aç/Kapat */}
      <TouchableOpacity style={styles.gerekceToggle} onPress={() => setGerekceAcik(v => !v)}>
        <Text style={styles.gerekceToggleText}>
          {gerekceAcik ? "▲ Gerekçeyi Gizle" : "▼ Değerlendirme Gerekçesi"}
        </Text>
      </TouchableOpacity>
      {gerekceAcik && (
        <Text style={styles.gerekceText}>{gerekce}</Text>
      )}
    </View>
  );
}

// ---------------------------------------------------------------------------
// Yükleniyor Ekranı (Skeleton + Spinner)
// ---------------------------------------------------------------------------

function YukleniyorEkrani({ istasyonAdi }) {
  const spinAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.loop(
      Animated.timing(spinAnim, { toValue: 1, duration: 1400, useNativeDriver: true, easing: Easing.linear })
    ).start();
  }, []);

  const rotate = spinAnim.interpolate({ inputRange: [0, 1], outputRange: ["0deg", "360deg"] });

  return (
    <ScrollView contentContainerStyle={styles.icerik} showsVerticalScrollIndicator={false}>

      {/* Yapay Zeka Spinner */}
      <View style={styles.aiSpinnerKapsayici}>
        <View style={styles.aiSpinnerDis}>
          <Animated.View style={[styles.aiSpinnerHalka, { transform: [{ rotate }] }]} />
          <View style={styles.aiSpinnerIc}>
            <MaterialCommunityIcons name="brain" size={28} color="#0056b3" />
          </View>
        </View>
        <Text style={styles.aiSpinnerBaslik}>Yapay Zeka Analiz Ediyor...</Text>
        <Text style={styles.aiSpinnerAlt}>
          {istasyonAdi} için kural motoru ve LLM{"\n"}değerlendirme yapılıyor
        </Text>
        <View style={styles.adimlariKapsayici}>
          {["Ölçüm kaydedildi ✓", "Kural motoru tamamlandı ✓", "LLM aksiyon önerisi hazırlanıyor..."].map((adim, i) => (
            <View key={i} style={styles.adimSatir}>
              <View style={[styles.adimNokta, i < 2 ? styles.adimNokTamamlandi : styles.adimNoktaBekliyor]} />
              <Text style={[styles.adimText, i < 2 ? styles.adimTextTamamlandi : styles.adimTextBekliyor]}>
                {adim}
              </Text>
            </View>
          ))}
        </View>
      </View>

      {/* Skeleton — rozet alanı */}
      <View style={styles.skeletonBolum}>
        <SkeletonBox w="100%" h={160} />
      </View>

      {/* Skeleton — anomali listesi */}
      <View style={styles.skeletonBolum}>
        <SkeletonBox w="60%" h={14} style={{ marginBottom: 12 }} />
        <SkeletonBox w="100%" h={64} style={{ marginBottom: 8 }} />
        <SkeletonBox w="100%" h={64} />
      </View>

      {/* Skeleton — LLM kart */}
      <View style={styles.skeletonBolum}>
        <SkeletonBox w="50%" h={14} style={{ marginBottom: 12 }} />
        <SkeletonBox w="100%" h={140} />
      </View>

    </ScrollView>
  );
}

// ---------------------------------------------------------------------------
// Ana Ekran
// ---------------------------------------------------------------------------

export default function SonucScreen({ navigation, route }) {
  const { olcumId, istasyon, ilkAnalizSonucu } = route.params;

  const [olcum, setOlcum] = useState(null);
  const [analizDurumu, setAnalizDurumu] = useState("BEKLİYOR");
  const [pollingHata, setPollingHata] = useState(false);

  const pollingRef    = useRef(null);
  const denemeRef     = useRef(0);
  const fadeAnim      = useRef(new Animated.Value(0)).current;
  const pulseAnim     = useRef(new Animated.Value(1)).current;

  // Sonuç geldiğinde fade-in animasyonu başlat
  const fadeIn = useCallback(() => {
    Animated.timing(fadeAnim, { toValue: 1, duration: 500, useNativeDriver: true }).start();
  }, [fadeAnim]);

  // KRİTİK için pulse
  const baslaPulse = useCallback(() => {
    Animated.loop(
      Animated.sequence([
        Animated.timing(pulseAnim, { toValue: 1.05, duration: 600, useNativeDriver: true }),
        Animated.timing(pulseAnim, { toValue: 1,    duration: 600, useNativeDriver: true }),
      ])
    ).start();
  }, [pulseAnim]);

  // Polling fonksiyonu
  const pollEt = useCallback(async () => {
    denemeRef.current += 1;

    if (denemeRef.current > POLLING_MAX_DENEME) {
      clearInterval(pollingRef.current);
      setPollingHata(true);
      return;
    }

    try {
      const veri = await getOlcum(olcumId);
      setOlcum(veri);

      if (veri.analiz_durumu === "TAMAMLANDI" || veri.analiz_durumu === "HATA") {
        clearInterval(pollingRef.current);
        setAnalizDurumu(veri.analiz_durumu);
        fadeIn();
        if (veri.risk_seviyesi === "KRİTİK") baslaPulse();
      }
    } catch (err) {
      console.warn("[Poll] İstek hatası:", err.message);
      // Bağlantı hatalarında polling'i durdurmuyoruz — retry mantığı var
    }
  }, [olcumId, fadeIn, baslaPulse]);

  useEffect(() => {
    // İlk yükleme — hemen bir kez çek
    pollEt();
    // Sonra her 3 saniyede bir
    pollingRef.current = setInterval(pollEt, POLLING_INTERVAL_MS);

    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, []);

  // ---------------------------------------------------------------------------
  // Render yardımcıları
  // ---------------------------------------------------------------------------

  const riskSeviyesi = olcum?.risk_seviyesi || "NORMAL";
  const konfig       = RISK_KONFIG[riskSeviyesi] || RISK_KONFIG.NORMAL;

  // Anomali detaylarını ilk API yanıtından veya ölçüm verisinden çek
  const anomaliDetaylari = ilkAnalizSonucu?.detaylar || [];

  // ---------------------------------------------------------------------------
  // HATA durumu
  // ---------------------------------------------------------------------------
  if (pollingHata || analizDurumu === "HATA") {
    return (
      <SafeAreaView style={styles.kapsayici}>
        <View style={styles.header}>
          <TouchableOpacity style={styles.geriBtn} onPress={() => navigation.popToTop()}>
            <Text style={styles.geriBtnText}>‹ Ana Sayfa</Text>
          </TouchableOpacity>
          <Text style={styles.headerBaslik}>Analiz Sonucu</Text>
          <Text style={styles.headerOlcumId}>#{olcumId}</Text>
        </View>
        <View style={styles.hataKapsayici}>
          <MaterialCommunityIcons name="alert-circle" size={56} color="#666666" style={styles.hataIkon} />
          <Text style={styles.hataBaslik}>Analiz Tamamlanamadı</Text>
          <Text style={styles.hataAlt}>
            {pollingHata
              ? "Analiz zaman aşımına uğradı. Sunucu durumunu kontrol edin."
              : "Arka plan işleminde beklenmeyen bir hata oluştu."}
          </Text>
          {olcum?.risk_seviyesi && (
            <View style={[styles.hataRozetKismi, { backgroundColor: RISK_KONFIG[olcum.risk_seviyesi]?.arkaplan }]}>
              <Text style={[styles.hataRozetText, { color: RISK_KONFIG[olcum.risk_seviyesi]?.renk }]}>
                Kural Motoru Sonucu: {olcum.risk_seviyesi}
              </Text>
            </View>
          )}
          <TouchableOpacity style={styles.yeniOlcumBtn} onPress={() => navigation.goBack()}>
            <Text style={styles.yeniOlcumBtnText}>+ Yeni Ölçüm Gir</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  // ---------------------------------------------------------------------------
  // BEKLİYOR durumu — Skeleton
  // ---------------------------------------------------------------------------
  if (analizDurumu === "BEKLİYOR" || !olcum) {
    return (
      <SafeAreaView style={styles.kapsayici}>
        <View style={styles.header}>
          <TouchableOpacity style={styles.geriBtn} onPress={() => navigation.popToTop()}>
            <Text style={styles.geriBtnText}>‹ Ana Sayfa</Text>
          </TouchableOpacity>
          <Text style={styles.headerBaslik}>Analiz Sonucu</Text>
          <Text style={styles.headerOlcumId}>#{olcumId}</Text>
        </View>
        <YukleniyorEkrani istasyonAdi={istasyon?.ad || "İstasyon"} />
      </SafeAreaView>
    );
  }

  // ---------------------------------------------------------------------------
  // TAMAMLANDI — Ana sonuç ekranı
  // ---------------------------------------------------------------------------
  return (
    <SafeAreaView style={styles.kapsayici}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity style={styles.geriBtn} onPress={() => navigation.popToTop()}>
          <Text style={styles.geriBtnText}>‹ Ana Sayfa</Text>
        </TouchableOpacity>
        <Text style={styles.headerBaslik}>Analiz Sonucu</Text>
        <Text style={styles.headerOlcumId}>#{olcumId}</Text>
      </View>

      <Animated.ScrollView
        style={{ opacity: fadeAnim }}
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.icerik}
      >
        {/* RİSK ROZETİ */}
        <Animated.View
          style={[
            styles.rozetKapsayici,
            { backgroundColor: konfig.arkaplan, borderColor: konfig.kenar },
            riskSeviyesi === "KRİTİK" && { transform: [{ scale: pulseAnim }] },
          ]}
        >
          <MaterialCommunityIcons name={konfig.ikon} size={56} color={konfig.renk} style={styles.rozetIkon} />
          <RenkRozeti riskSeviyesi={riskSeviyesi} />
          <Text style={styles.rozetAciklama}>{konfig.aciklama}</Text>
          <View style={styles.istasyonSatir}>
            <MaterialCommunityIcons name="map-marker" size={16} color="#333333" style={{marginRight: 4}} />
            <Text style={styles.istasyonSatirText}>{istasyon?.ad || "İstasyon"}</Text>
          </View>
        </Animated.View>

        {/* ANOMALİ DETAYLARI */}
        {anomaliDetaylari.length > 0 && (
          <View style={styles.bolum}>
            <Text style={styles.bolumBaslik}>Tespit Edilen Anomaliler</Text>
            {anomaliDetaylari.map((d, i) => {
              const dKonfig = RISK_KONFIG[d.risk] || RISK_KONFIG.NORMAL;
              return (
                <View key={i} style={[styles.anomaliSatir, { borderLeftColor: dKonfig.renk }]}>
                  <View style={styles.anomaliHeader}>
                    <MaterialCommunityIcons name={dKonfig.ikon} size={18} color={dKonfig.renk} style={styles.anomaliIkon} />
                    <Text style={[styles.anomaliKural, { color: dKonfig.renk }]}>{d.kural}</Text>
                    <View style={[styles.anomaliRiskBadge, { backgroundColor: dKonfig.arkaplan, borderColor: dKonfig.kenar }]}>
                      <Text style={[styles.anomaliRiskText, { color: dKonfig.renk }]}>{d.risk}</Text>
                    </View>
                  </View>
                  <Text style={styles.anomaliMesaj}>{d.mesaj}</Text>
                </View>
              );
            })}
          </View>
        )}

        {/* LLM TEKNİK AKSİYON ÖNERİSİ KARTI */}
        <View style={styles.bolum}>
          <View style={styles.llmBaslikSatir}>
            <Text style={styles.bolumBaslik}>Teknik Aksiyon Önerisi</Text>
            <View style={styles.llmBadge}>
              <Text style={styles.llmBadgeText}>AI ✓</Text>
            </View>
          </View>
          <View style={styles.llmKart}>
            <Text style={styles.llmOneri}>
              {olcum.aksiyon_onerisi || "Aksiyon önerisi mevcut değil."}
            </Text>
          </View>
        </View>

        {/* AI GÜVENİLİRLİK PUANI — LLM-as-a-Judge */}
        {olcum.metrikler && (
          <GuvenilirlikPuaniKarti metrikler={olcum.metrikler} />
        )}

        {/* Ölçüm özeti */}
        <View style={styles.bolum}>
          <Text style={styles.bolumBaslik}>Ölçüm Özeti</Text>
          <View style={styles.olcumOzetGrid}>
            {[
              { etiket: "pH",         deger: olcum.ph,           birim: "" },
              { etiket: "Klor",       deger: olcum.serbest_klor, birim: " mg/L" },
              { etiket: "Bulanıklık", deger: olcum.bulaniklik,   birim: " NTU" },
              { etiket: "İletkenlik", deger: olcum.iletkenlik,   birim: " µS/cm" },
              { etiket: "Sıcaklık",  deger: olcum.sicaklik,     birim: " °C" },
            ].filter(p => p.deger !== null && p.deger !== undefined).map((p, i) => (
              <View key={i} style={styles.olcumOzetKarti}>
                <Text style={styles.olcumOzetEtiket}>{p.etiket}</Text>
                <Text style={styles.olcumOzetDeger}>{p.deger}{p.birim}</Text>
              </View>
            ))}
          </View>
        </View>

        {/* Butonlar */}
        <TouchableOpacity style={styles.yeniOlcumBtn} onPress={() => navigation.goBack()} activeOpacity={0.85}>
          <Text style={styles.yeniOlcumBtnText}>+ Yeni Ölçüm Gir</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.anaSayfaBtn} onPress={() => navigation.popToTop()} activeOpacity={0.85}>
          <MaterialCommunityIcons name="home-outline" size={20} color="#666666" style={{marginRight: 8}} />
          <Text style={styles.anaSayfaBtnText}>İstasyon Listesine Dön</Text>
        </TouchableOpacity>
      </Animated.ScrollView>
    </SafeAreaView>
  );
}

// ---------------------------------------------------------------------------
// Stiller
// ---------------------------------------------------------------------------

const styles = StyleSheet.create({
  kapsayici: { flex: 1, backgroundColor: "#F8F9FA" },
  header: {
    flexDirection: "row", alignItems: "center", justifyContent: "space-between",
    paddingHorizontal: 16, paddingVertical: 14,
    borderBottomWidth: 1, borderBottomColor: "rgba(0,0,0,0.05)",
    backgroundColor: "#FFFFFF"
  },
  geriBtn: { padding: 8 },
  geriBtnText: { color: "#0056b3", fontSize: 16, fontWeight: "600" },
  headerBaslik: { fontSize: 18, fontWeight: "700", color: "#333333" },
  headerOlcumId: { fontSize: 14, color: "#666666", fontWeight: "600" },
  icerik: { padding: 16, paddingBottom: 48 },

  // ---- Spinner / Loading ----
  aiSpinnerKapsayici: {
    alignItems: "center", paddingVertical: 28,
    backgroundColor: "#FFFFFF", borderRadius: 16,
    borderWidth: 1, borderColor: "rgba(0,0,0,0.05)", marginBottom: 20,
    shadowColor: "#000", shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.05, shadowRadius: 4, elevation: 2
  },
  aiSpinnerDis: { width: 80, height: 80, justifyContent: "center", alignItems: "center", marginBottom: 16 },
  aiSpinnerHalka: {
    position: "absolute", width: 80, height: 80, borderRadius: 40,
    borderWidth: 3, borderColor: "transparent",
    borderTopColor: "#0056b3", borderRightColor: "rgba(0,86,179,0.4)",
  },
  aiSpinnerIc: {
    width: 56, height: 56, borderRadius: 28,
    backgroundColor: "rgba(0,86,179,0.1)", justifyContent: "center", alignItems: "center",
  },
  aiSpinnerIkon: { fontSize: 26 },
  aiSpinnerBaslik: { fontSize: 18, fontWeight: "700", color: "#333333", marginBottom: 6 },
  aiSpinnerAlt: { fontSize: 13, color: "#666666", textAlign: "center", lineHeight: 20, marginBottom: 20 },
  adimlariKapsayici: { alignSelf: "stretch", paddingHorizontal: 24, gap: 8 },
  adimSatir: { flexDirection: "row", alignItems: "center", gap: 10 },
  adimNokta: { width: 8, height: 8, borderRadius: 4 },
  adimNokTamamlandi: { backgroundColor: "#28A745" },
  adimNoktaBekliyor: { backgroundColor: "#0056b3" },
  adimText: { fontSize: 13 },
  adimTextTamamlandi: { color: "#28A745" },
  adimTextBekliyor: { color: "#0056b3" },

  // ---- Skeleton ----
  skeletonBolum: { marginBottom: 20 },

  // ---- Hata ekranı ----
  hataKapsayici: { flex: 1, justifyContent: "center", alignItems: "center", padding: 32, gap: 12 },
  hataIkon: { marginBottom: 8 },
  hataBaslik: { fontSize: 20, fontWeight: "700", color: "#333333" },
  hataAlt: { fontSize: 14, color: "#666666", textAlign: "center", lineHeight: 20 },
  hataRozetKismi: { borderRadius: 12, paddingHorizontal: 16, paddingVertical: 8, marginTop: 8 },
  hataRozetText: { fontSize: 14, fontWeight: "700" },

  // ---- Rozet ----
  rozetKapsayici: {
    backgroundColor: "#FFFFFF", borderRadius: 16, padding: 24,
    alignItems: "center", marginBottom: 20,
    borderWidth: 1, borderColor: "rgba(0,0,0,0.05)",
    shadowColor: "#000", shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.05, shadowRadius: 4, elevation: 2
  },
  rozetIkon: { marginBottom: 16 },
  rozetAciklama: { fontSize: 15, color: "#666666", textAlign: "center", lineHeight: 22, marginTop: 16 },
  istasyonSatir: {
    marginTop: 16, backgroundColor: "#F8F9FA", flexDirection: "row", alignItems: "center",
    borderRadius: 8, paddingHorizontal: 16, paddingVertical: 8,
  },
  istasyonSatirText: { fontSize: 14, color: "#333333", fontWeight: "600" },

  // ---- Bölüm ----
  bolum: { marginBottom: 20 },
  bolumBaslik: {
    fontSize: 14, fontWeight: "700", color: "#666666",
    letterSpacing: 1, textTransform: "uppercase", marginBottom: 12,
  },

  // ---- Anomali ----
  anomaliSatir: {
    backgroundColor: "#FFFFFF", borderRadius: 12, padding: 14,
    marginBottom: 8, borderLeftWidth: 4,
    shadowColor: "#000", shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.05, shadowRadius: 2, elevation: 1
  },
  anomaliHeader: { flexDirection: "row", alignItems: "center", marginBottom: 6, gap: 8 },
  anomaliIkon: { marginRight: 2 },
  anomaliKural: { fontSize: 14, fontWeight: "700", flex: 1 },
  anomaliRiskBadge: { borderWidth: 1, borderRadius: 6, paddingHorizontal: 6, paddingVertical: 2 },
  anomaliRiskText: { fontSize: 10, fontWeight: "700" },
  anomaliMesaj: { fontSize: 14, color: "#666666", lineHeight: 20 },

  // ---- LLM Kart ----
  llmBaslikSatir: { flexDirection: "row", alignItems: "center", marginBottom: 12, gap: 8 },
  llmBadge: {
    backgroundColor: "#E3F2FD", borderRadius: 6,
    paddingHorizontal: 8, paddingVertical: 3, borderWidth: 1, borderColor: "#BBDEFB",
  },
  llmBadgeText: { color: "#0056b3", fontSize: 11, fontWeight: "800", letterSpacing: 1 },
  llmKart: {
    backgroundColor: "#FFFFFF", borderRadius: 16, padding: 20,
    borderWidth: 1, borderColor: "rgba(0,0,0,0.05)",
    shadowColor: "#000", shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.05, shadowRadius: 4, elevation: 2
  },
  llmOneri: { color: "#333333", fontSize: 15, lineHeight: 24, fontWeight: "500" },

  // ---- Ölçüm Özet Grid ----
  olcumOzetGrid: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  olcumOzetKarti: {
    backgroundColor: "#FFFFFF", borderRadius: 12, padding: 14,
    alignItems: "center", minWidth: "30%", flex: 1,
    borderWidth: 1, borderColor: "rgba(0,0,0,0.05)",
    shadowColor: "#000", shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.05, shadowRadius: 2, elevation: 1
  },
  olcumOzetEtiket: { fontSize: 12, color: "#666666", marginBottom: 4, fontWeight: "600" },
  olcumOzetDeger: { fontSize: 16, fontWeight: "700", color: "#333333" },

  // ---- Güvenilirlik Puanı Kartı ----
  guvenBolum: {
    borderRadius: 16, borderWidth: 1, borderColor: "rgba(0,0,0,0.05)", padding: 18, marginBottom: 20,
    backgroundColor: "#FFFFFF", shadowColor: "#000", shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.05, shadowRadius: 4, elevation: 2
  },
  guvenBaslikSatir: {
    flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 12,
  },
  guvenBaslik: {
    fontSize: 14, fontWeight: "700", color: "#666666",
    letterSpacing: 1, textTransform: "uppercase",
  },
  guvenRozetBadge: {
    borderWidth: 1, borderRadius: 10, paddingHorizontal: 10, paddingVertical: 4,
  },
  guvenRozetText: { fontSize: 12, fontWeight: "800" },
  guvenUyariKutusu: {
    backgroundColor: "#FFEBEE", borderRadius: 10, padding: 10,
    borderWidth: 1, borderColor: "#FFCDD2", marginBottom: 12, flexDirection: "row", alignItems: "flex-start",
  },
  guvenUyariText: { color: "#DC3545", fontSize: 13, lineHeight: 18, fontWeight: "600", flex: 1 },
  guvenPuanSatir: {
    flexDirection: "row", alignItems: "center", gap: 8, marginBottom: 14,
  },
  guvenPuan: { fontSize: 38, fontWeight: "900", letterSpacing: -1 },
  guvenPuanBirim: { fontSize: 16, color: "#999999", alignSelf: "flex-end", marginBottom: 6 },
  guvenBarKapsayici: {
    flex: 1, height: 8, backgroundColor: "#E0E0E0",
    borderRadius: 4, overflow: "hidden",
  },
  guvenBar: { height: "100%", borderRadius: 4 },
  gerekceToggle: { paddingVertical: 6 },
  gerekceToggleText: { fontSize: 14, color: "#0056b3", fontWeight: "600" },
  gerekceText: {
    fontSize: 14, color: "#666666", lineHeight: 22,
    marginTop: 8, paddingTop: 12,
    borderTopWidth: 1, borderTopColor: "rgba(0,0,0,0.05)",
  },

  // ---- Butonlar ----
  yeniOlcumBtn: {
    backgroundColor: "#0056b3", borderRadius: 12, paddingVertical: 18,
    alignItems: "center", marginBottom: 12,
    shadowColor: "#0056b3", shadowOffset: { width: 0, height: 4 }, shadowOpacity: 0.2, shadowRadius: 8, elevation: 4,
  },
  yeniOlcumBtnText: { color: "#FFFFFF", fontSize: 18, fontWeight: "700" },
  anaSayfaBtn: {
    backgroundColor: "#FFFFFF", borderRadius: 12, paddingVertical: 18,
    alignItems: "center", justifyContent: "center", flexDirection: "row", borderWidth: 1, borderColor: "#E0E0E0",
  },
  anaSayfaBtnText: { color: "#666666", fontSize: 16, fontWeight: "700" },
});
