import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, ActivityIndicator, ScrollView, TouchableOpacity, Dimensions } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { LineChart } from 'react-native-chart-kit';
import { getStationHistory, getTrendAnalysis } from '../services/api';

export default function StationHistoryScreen({ route, navigation }) {
  const { station_id, station_ad } = route.params || {};
  const [loading, setLoading] = useState(true);
  const [measurements, setMeasurements] = useState([]);
  const [trendData, setTrendData] = useState(null);
  
  useEffect(() => {
    const loadData = async () => {
      try {
        const [history, trend] = await Promise.all([
          getStationHistory(station_id),
          getTrendAnalysis(station_id).catch(() => null)
        ]);
        
        // history is newest first, we want oldest first for charting
        const sortedHistory = [...history].sort((a, b) => new Date(a.olcum_tarihi) - new Date(b.olcum_tarihi));
        setMeasurements(sortedHistory);
        
        // trend is { measurements: [...] }
        if (trend && trend.measurements && trend.measurements.length > 0) {
           setTrendData(trend.measurements[0]); // newest trend info
        }
      } catch (err) {
        console.error("Error loading history", err);
      } finally {
        setLoading(false);
      }
    };
    if (station_id) loadData();
  }, [station_id]);

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#0056b3" />
        <Text style={styles.loadingText}>Veriler Yükleniyor...</Text>
      </View>
    );
  }

  // Formatting data for react-native-chart-kit
  const pad = (n) => n.toString().padStart(2, '0');
  const labels = measurements.map(m => {
    const t = new Date(m.olcum_tarihi);
    return `${pad(t.getHours())}:${pad(t.getMinutes())}`;
  });

  const phDataArr = measurements.map(m => m.ph || 0);
  const klorDataArr = measurements.map(m => m.serbest_klor || 0);
  const bulaniklikDataArr = measurements.map(m => m.bulaniklik || 0);

  const chartData = {
    labels: labels.length > 6 ? labels.filter((_, i) => i % Math.ceil(labels.length / 6) === 0) : labels,
    datasets: [
      {
        data: phDataArr.length > 0 ? phDataArr : [0],
        color: (opacity = 1) => `rgba(52, 152, 219, ${opacity})`, // #3498DB
        strokeWidth: 2
      },
      {
        data: klorDataArr.length > 0 ? klorDataArr : [0],
        color: (opacity = 1) => `rgba(155, 89, 182, ${opacity})`, // #9B59B6
        strokeWidth: 2
      },
      {
        data: bulaniklikDataArr.length > 0 ? bulaniklikDataArr : [0],
        color: (opacity = 1) => `rgba(26, 188, 156, ${opacity})`, // #1ABC9C
        strokeWidth: 2
      }
    ],
    legend: ["pH", "Klor", "Bulanıklık"]
  };

  let forecastColor = "#27AE60"; // green
  let trendMessage = "Değerler normal seyrinde devam ediyor.";

  if (measurements.length > 0 && trendData) {
    const score = trendData.trend_risk_score || 0;
    const direction = trendData.trend_direction || "STABİL";
    
    if (score > 70) {
       forecastColor = "#E74C3C"; // red
       trendMessage = "Kritik seviyede anomali! Acil müdahale önerilir.";
    } else if (score >= 40) {
       forecastColor = "#E67E22"; // amber
       trendMessage = direction === "YÜKSELİŞ" ? "Değerler yükseliş trendinde, kritik eşiğe yaklaşıyor." : "Değerler düşüş trendinde, dikkatle izlenmeli.";
    }
  }

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <TouchableOpacity style={styles.backBtn} onPress={() => navigation.goBack()}>
          <MaterialCommunityIcons name="arrow-left" size={24} color="#0056b3" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>{station_ad || 'İstasyon'} - Geçmiş Veriler</Text>
      </View>

      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <View style={styles.chartCard}>
          <Text style={styles.chartTitle}>Son Ölçüm Trendleri</Text>
          
          <LineChart
            data={chartData}
            width={Dimensions.get("window").width - 64} // padding considerations
            height={220}
            chartConfig={{
              backgroundColor: "#FFF",
              backgroundGradientFrom: "#FFF",
              backgroundGradientTo: "#FFF",
              decimalPlaces: 1,
              color: (opacity = 1) => `rgba(0, 0, 0, ${opacity})`,
              labelColor: (opacity = 1) => `rgba(0, 0, 0, ${opacity})`,
              style: {
                borderRadius: 16
              },
              propsForDots: {
                r: "3",
                strokeWidth: "2",
                stroke: "#FFF"
              }
            }}
            bezier
            style={{
              marginVertical: 8,
              borderRadius: 16
            }}
          />
        </View>

        <View style={[styles.trendCard, { borderLeftColor: forecastColor, borderLeftWidth: 4 }]}>
          <Text style={styles.trendTitle}>Yapay Zeka Trend Analizi</Text>
          <Text style={styles.trendDesc}>{trendMessage}</Text>
          
          {/* Önceden backend'de hesaplanıp response'a dahil edilmeyen projected_value ve projection_message artık kullanıcıya sunuluyor */}
          {trendData && trendData.projection_message ? (
            <Text style={styles.projectionMessage}>{trendData.projection_message}</Text>
          ) : null}

          {trendData && trendData.projected_value != null && (
            <View style={styles.projectedValueRow}>
              <MaterialCommunityIcons name="crystal-ball" size={16} color={forecastColor} style={{ marginRight: 6 }} />
              <Text style={styles.projectedValueText}>
                Beklenen bir sonraki değer: <Text style={{ fontWeight: '700', color: '#1A1A1A' }}>{trendData.projected_value.toFixed(2)}</Text>
              </Text>
            </View>
          )}

          {trendData && trendData.trend_risk_score > 0 && (
            <Text style={styles.trendScore}>
              Risk Skoru: <Text style={{ color: forecastColor, fontWeight: 'bold' }}>{trendData.trend_risk_score}</Text>
            </Text>
          )}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F8F9FA' },
  loadingContainer: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  loadingText: { marginTop: 10, color: '#555' },
  header: {
    flexDirection: 'row', alignItems: 'center',
    paddingHorizontal: 16, paddingVertical: 16,
    backgroundColor: '#FFFFFF',
    borderBottomWidth: 1, borderBottomColor: 'rgba(0,0,0,0.05)',
  },
  backBtn: { padding: 4, marginRight: 8 },
  headerTitle: { fontSize: 18, fontWeight: '700', color: '#0056b3' },
  content: { padding: 16 },
  chartCard: {
    backgroundColor: '#FFF',
    borderRadius: 12,
    padding: 16,
    marginBottom: 16,
    elevation: 3,
    shadowColor: '#000', shadowOpacity: 0.1, shadowRadius: 5, shadowOffset: { width: 0, height: 2 }
  },
  chartTitle: { fontSize: 16, fontWeight: 'bold', color: '#333', marginBottom: 10 },
  trendCard: {
    backgroundColor: '#FFF',
    borderRadius: 12,
    padding: 16,
    elevation: 2,
    shadowColor: '#000', shadowOpacity: 0.05, shadowRadius: 4, shadowOffset: { width: 0, height: 2 }
  },
  trendTitle: { fontSize: 15, fontWeight: 'bold', color: '#333', marginBottom: 8 },
  trendDesc: { fontSize: 14, color: '#555', lineHeight: 20 },
  projectionMessage: { fontSize: 13, color: '#444', fontStyle: 'italic', marginTop: 6, lineHeight: 18 },
  projectedValueRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 8,
    backgroundColor: 'rgba(0,0,0,0.03)',
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
  },
  projectedValueText: { fontSize: 13, color: '#444' },
  trendScore: { fontSize: 13, color: '#777', marginTop: 8 }
});
