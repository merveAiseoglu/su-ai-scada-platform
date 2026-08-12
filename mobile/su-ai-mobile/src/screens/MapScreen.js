// screens/MapScreen.js
// GIS Harita Ekranı — Faz 3
// Callout yerine onPress + bottom panel (Android/iOS uyumlu)

import React, { useState, useCallback, useEffect } from 'react';
import {
  View, StyleSheet, Text, ActivityIndicator,
  TouchableOpacity, ScrollView, Modal, Pressable,
} from 'react-native';
import MapView, { Marker } from 'react-native-maps';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useFocusEffect } from '@react-navigation/native';
import { getGisIstasyonlar, getUserInfo } from '../services/api';

// ---------------------------------------------------------------------------
// Risk → görsel eşleşme
// ---------------------------------------------------------------------------
const RISK_KONFIG = {
  KRİTİK: { renk: '#E74C3C', bg: '#FDEDEC', etiket: 'KRİTİK', pin: 'red',    ikon: 'alert-circle' },
  ORTA:   { renk: '#E67E22', bg: '#FEF3E7', etiket: 'ORTA',   pin: 'orange', ikon: 'alert' },
  DÜŞÜK:  { renk: '#F1C40F', bg: '#FEFCE8', etiket: 'DÜŞÜK',  pin: 'yellow', ikon: 'information' },
  NORMAL: { renk: '#27AE60', bg: '#EAFAF1', etiket: 'NORMAL', pin: 'green',  ikon: 'check-circle' },
};
function getKonfig(risk) {
  return RISK_KONFIG[risk] || RISK_KONFIG['NORMAL'];
}

// ---------------------------------------------------------------------------
// Sensör satırı
// ---------------------------------------------------------------------------
function SatirRow({ label, value, birim, uyari }) {
  if (value == null) return null;
  return (
    <View style={panel.row}>
      <Text style={panel.rowLabel}>{label}</Text>
      <Text style={[panel.rowValue, uyari && panel.rowUyari]}>
        {typeof value === 'number' ? value.toFixed(2) : value}{birim ? ' ' + birim : ''}
      </Text>
    </View>
  );
}

// ---------------------------------------------------------------------------
// Ana ekran
// ---------------------------------------------------------------------------
export default function MapScreen({ navigation }) {
  const [istasyonlar, setIstasyonlar] = useState([]);
  const [yukleniyor, setYukleniyor]   = useState(true);
  const [secili, setSecili]           = useState(null); // seçili istasyon (bottom panel)
  const [userInfo, setUserInfo]       = useState(null);

  useEffect(() => {
    getUserInfo().then(info => setUserInfo(info));
  }, []);

  // Her odaklanmada yenile — simülasyon sonrası renkler güncellensin
  useFocusEffect(
    useCallback(() => {
      let aktif = true;
      setYukleniyor(true);
      getGisIstasyonlar()
        .then(data  => { if (aktif) setIstasyonlar(data); })
        .catch(() => {})
        .finally(() => { if (aktif) setYukleniyor(false); });
      return () => { aktif = false; };
    }, [])
  );

  const yenile = useCallback(() => {
    setYukleniyor(true);
    getGisIstasyonlar()
      .then(data => setIstasyonlar(data))
      .catch(() => {})
      .finally(() => setYukleniyor(false));
  }, []);

  const kritikSayisi = istasyonlar.filter(i => i.son_risk_seviyesi === 'KRİTİK').length;
  const ortaSayisi   = istasyonlar.filter(i => i.son_risk_seviyesi === 'ORTA').length;

  return (
    <View style={styles.container}>
      {/* ── Header ── */}
      <View style={styles.header}>
        <TouchableOpacity style={styles.backBtn} onPress={() => navigation.goBack()}>
          <MaterialCommunityIcons name="arrow-left" size={24} color="#0056b3" />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={styles.headerTitle}>Istasyon Haritasi (GIS)</Text>
          <Text style={styles.headerAlt}>{istasyonlar.length} istasyon</Text>
        </View>
        <TouchableOpacity style={styles.refreshBtn} onPress={yenile}>
          <MaterialCommunityIcons name={yukleniyor ? 'loading' : 'refresh'} size={22} color="#0056b3" />
        </TouchableOpacity>
      </View>

      {/* ── Risk Ozet Cubugu ── */}
      {!yukleniyor && (
        <View style={styles.ozet}>
          {kritikSayisi > 0 && (
            <View style={[styles.ozetBadge, { borderColor: '#E74C3C', backgroundColor: '#FDEDEC' }]}>
              <Text style={[styles.ozetText, { color: '#E74C3C' }]}>{kritikSayisi} KRITIK</Text>
            </View>
          )}
          {ortaSayisi > 0 && (
            <View style={[styles.ozetBadge, { borderColor: '#E67E22', backgroundColor: '#FEF3E7' }]}>
              <Text style={[styles.ozetText, { color: '#E67E22' }]}>{ortaSayisi} ORTA</Text>
            </View>
          )}
          {kritikSayisi === 0 && ortaSayisi === 0 && (
            <View style={[styles.ozetBadge, { borderColor: '#27AE60', backgroundColor: '#EAFAF1' }]}>
              <Text style={[styles.ozetText, { color: '#27AE60' }]}>Tum istasyonlar normal</Text>
            </View>
          )}
        </View>
      )}

      {/* ── Harita ── */}
      {yukleniyor ? (
        <View style={styles.loadingBox}>
          <ActivityIndicator size="large" color="#0056b3" />
          <Text style={styles.loadingText}>Harita yukleniyor...</Text>
        </View>
      ) : (
        <MapView
          style={styles.map}
          initialRegion={{
            latitude: 37.1674,
            longitude: 38.7955,
            latitudeDelta: 0.12,
            longitudeDelta: 0.12,
          }}
          onPress={() => setSecili(null)}   // Haritaya basınca paneli kapat
        >
          {istasyonlar.map(ist => {
            if (!ist.enlem || !ist.boylam) return null;
            const konfig = getKonfig(ist.son_risk_seviyesi);
            return (
              <Marker
                key={ist.id}
                coordinate={{ latitude: ist.enlem, longitude: ist.boylam }}
                pinColor={konfig.pin}
                tracksViewChanges={false}
                onPress={(e) => {
                  e.stopPropagation();
                  // Her rol için markera basınca paneli aç
                  setSecili(ist);
                }}
              />
            );
          })}
        </MapView>
      )}

      {/* ── Bottom Panel (Callout yerine) ── */}
      {secili && (
        <View style={panel.container} pointerEvents="box-none">
          <View style={panel.card}>
            {/* Kapat butonu */}
            <TouchableOpacity style={panel.kapatBtn} onPress={() => setSecili(null)}>
              <MaterialCommunityIcons name="close" size={20} color="#999" />
            </TouchableOpacity>

            {/* Baslik + Risk */}
            <View style={panel.baslikSatir}>
              <View style={{ flex: 1 }}>
                <Text style={panel.ad}>{secili.ad}</Text>
                <Text style={panel.tip}>{secili.tip} — {secili.konum || 'Konum yok'}</Text>
              </View>
              {(() => {
                const k = getKonfig(secili.son_risk_seviyesi);
                return (
                  <View style={[panel.riskBadge, { backgroundColor: k.bg, borderColor: k.renk }]}>
                    <MaterialCommunityIcons name={k.ikon} size={14} color={k.renk} />
                    <Text style={[panel.riskText, { color: k.renk }]}>{k.etiket}</Text>
                  </View>
                );
              })()}
            </View>

            {/* Sensor Verileri */}
            {(secili.son_ph != null || secili.son_serbest_klor != null ||
              secili.son_bulaniklik != null || secili.son_iletkenlik != null ||
              secili.son_sicaklik != null) ? (
              <View style={panel.sensorBox}>
                <Text style={panel.sensorBaslik}>SON OLCUM DEGERLERI</Text>
                <SatirRow label="pH"          value={secili.son_ph}           birim=""       uyari={secili.son_ph != null && (secili.son_ph < 6.5 || secili.son_ph > 8.5)} />
                <SatirRow label="Serbest Klor" value={secili.son_serbest_klor} birim="mg/L"  uyari={secili.son_serbest_klor != null && secili.son_serbest_klor < 0.2} />
                <SatirRow label="Bulaniklik"   value={secili.son_bulaniklik}   birim="NTU"   uyari={secili.son_bulaniklik != null && secili.son_bulaniklik > 1.0} />
                <SatirRow label="Iletkenlik"   value={secili.son_iletkenlik}   birim="uS/cm" uyari={secili.son_iletkenlik != null && secili.son_iletkenlik > 500} />
                <SatirRow label="Sicaklik"     value={secili.son_sicaklik}     birim="C"     uyari={false} />
              </View>
            ) : (
              <Text style={panel.olcumYok}>Bu istasyon icin henuz olcum yapilmamis.</Text>
            )}

            {/* Alt Satır: Tarih ve Buton */}
            <View style={panel.altSatir}>
              {secili.son_olcum_tarihi ? (
                <Text style={panel.tarih}>
                  Son olcum: {new Date(secili.son_olcum_tarihi).toLocaleString('tr-TR')}
                </Text>
              ) : (
                <View style={{ flex: 1 }} />
              )}
              
              {/* Analiz Butonu (Sadece Yönetici) veya Ölçüm Gir Butonu (Personel) */}
              {userInfo?.rol === 'yonetici' ? (
                <TouchableOpacity
                  style={panel.analizBtn}
                  onPress={() => navigation.navigate('StationHistoryScreen', { station_id: secili.id, station_ad: secili.ad })}
                >
                  <MaterialCommunityIcons name="chart-line" size={14} color="#FFF" style={{ marginRight: 4 }} />
                  <Text style={panel.analizBtnText}>Analizi Gör</Text>
                </TouchableOpacity>
              ) : (
                <TouchableOpacity
                  style={[panel.analizBtn, { backgroundColor: '#28A745' }]}
                  onPress={() => navigation.navigate("MeasurementForm", { istasyon: secili })}
                >
                  <MaterialCommunityIcons name="plus" size={14} color="#FFF" style={{ marginRight: 4 }} />
                  <Text style={panel.analizBtnText}>Ölçüm Gir</Text>
                </TouchableOpacity>
              )}
            </View>
          </View>
        </View>
      )}
    </View>
  );
}

// ---------------------------------------------------------------------------
// Stiller
// ---------------------------------------------------------------------------
const styles = StyleSheet.create({
  container:   { flex: 1, backgroundColor: '#F8F9FA' },
  header: {
    flexDirection: 'row', alignItems: 'center',
    paddingHorizontal: 16, paddingTop: 48, paddingBottom: 12,
    backgroundColor: '#FFFFFF',
    borderBottomWidth: 1, borderBottomColor: 'rgba(0,0,0,0.07)',
    elevation: 3,
  },
  backBtn:     { padding: 6, marginRight: 10 },
  headerTitle: { fontSize: 17, fontWeight: '700', color: '#0056b3' },
  headerAlt:   { fontSize: 11, color: '#888', marginTop: 1 },
  refreshBtn:  { padding: 6, marginLeft: 6 },
  ozet: {
    flexDirection: 'row', flexWrap: 'wrap', gap: 6,
    paddingHorizontal: 12, paddingVertical: 8,
    backgroundColor: '#FFF',
    borderBottomWidth: 1, borderBottomColor: 'rgba(0,0,0,0.05)',
  },
  ozetBadge: {
    paddingHorizontal: 10, paddingVertical: 3,
    borderRadius: 20, borderWidth: 1,
  },
  ozetText:    { fontSize: 12, fontWeight: '700' },
  map:         { flex: 1 },
  loadingBox:  { flex: 1, justifyContent: 'center', alignItems: 'center', gap: 12 },
  loadingText: { color: '#555', fontSize: 15 },
});

const panel = StyleSheet.create({
  container: {
    position: 'absolute', bottom: 0, left: 0, right: 0,
    paddingHorizontal: 12, paddingBottom: 24,
  },
  card: {
    backgroundColor: '#FFF',
    borderRadius: 16,
    padding: 16,
    elevation: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: -2 },
    shadowOpacity: 0.15,
    shadowRadius: 10,
  },
  kapatBtn: {
    position: 'absolute', top: 12, right: 12,
    padding: 4, zIndex: 10,
  },
  baslikSatir:  { flexDirection: 'row', alignItems: 'flex-start', marginBottom: 10, paddingRight: 28 },
  ad:           { fontSize: 16, fontWeight: '700', color: '#1A1A2E' },
  tip:          { fontSize: 12, color: '#888', marginTop: 2 },
  riskBadge: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    borderRadius: 8, borderWidth: 1,
    paddingHorizontal: 8, paddingVertical: 4,
    marginLeft: 8,
  },
  riskText:     { fontSize: 11, fontWeight: '700' },
  sensorBox: {
    backgroundColor: '#F8F9FA', borderRadius: 10,
    padding: 10, marginBottom: 8,
    borderWidth: 1, borderColor: '#ECECEC',
  },
  sensorBaslik: { fontSize: 10, fontWeight: '700', color: '#888', marginBottom: 6, letterSpacing: 0.5 },
  row:          { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 4 },
  rowLabel:     { fontSize: 13, color: '#555' },
  rowValue:     { fontSize: 13, fontWeight: '600', color: '#1A1A2E' },
  rowUyari:     { color: '#E74C3C' },
  olcumYok:     { fontSize: 13, color: '#999', fontStyle: 'italic', marginBottom: 6 },
  altSatir:     { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-end', marginTop: 4 },
  tarih:        { fontSize: 11, color: '#AAA' },
  analizBtn: {
    backgroundColor: '#0056b3', borderRadius: 8, paddingHorizontal: 12, paddingVertical: 6,
    flexDirection: 'row', alignItems: 'center',
  },
  analizBtnText: { color: '#FFF', fontSize: 11, fontWeight: '700' },
});
