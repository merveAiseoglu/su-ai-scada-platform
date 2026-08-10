import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, ActivityIndicator, ScrollView, TouchableOpacity } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { VictoryChart, VictoryLine, VictoryTheme, VictoryAxis, VictoryLegend } from 'victory-native';
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

  // Formatting data for Victory
  const phData = measurements.map(m => ({ x: new Date(m.olcum_tarihi), y: m.ph || 0 }));
  const klorData = measurements.map(m => ({ x: new Date(m.olcum_tarihi), y: m.serbest_klor || 0 }));
  const bulaniklikData = measurements.map(m => ({ x: new Date(m.olcum_tarihi), y: m.bulaniklik || 0 }));

  // Mocking forecast point since API doesn't provide `projected_value`
  let forecastData = [];
  let forecastColor = "#27AE60"; // green
  let trendMessage = "Değerler normal seyrinde devam ediyor.";

  if (measurements.length > 0 && trendData) {
    const lastPoint = measurements[measurements.length - 1];
    const score = trendData.trend_risk_score || 0;
    const direction = trendData.trend_direction || "STABİL";
    
    if (score > 70) {
       forecastColor = "#E74C3C"; // red
       trendMessage = "Kritik seviyede anomali! Acil müdahale önerilir.";
    } else if (score >= 40) {
       forecastColor = "#E67E22"; // amber
       trendMessage = direction === "YÜKSELİŞ" ? "Değerler yükseliş trendinde, kritik eşiğe yaklaşıyor." : "Değerler düşüş trendinde, dikkatle izlenmeli.";
    }

    // Mock next point time (+2 hours)
    const nextTime = new Date(new Date(lastPoint.olcum_tarihi).getTime() + 2 * 60 * 60 * 1000);
    // Mock next value based on direction (we'll just use pH as the main driver for the visual dashed line since we don't know which param has the anomaly)
    let nextValue = lastPoint.ph || 7.2;
    if (direction === "YÜKSELİŞ") nextValue *= 1.05;
    if (direction === "DÜŞÜŞ") nextValue *= 0.95;
    
    forecastData = [
       { x: new Date(lastPoint.olcum_tarihi), y: lastPoint.ph || 0 },
       { x: nextTime, y: nextValue }
    ];
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
          
          <VictoryChart 
            theme={VictoryTheme.material} 
            height={300}
            padding={{ top: 50, bottom: 50, left: 50, right: 30 }}
            scale={{ x: "time" }}
          >
            <VictoryLegend x={50} y={10}
              orientation="horizontal"
              symbolSpacer={5}
              gutter={20}
              data={[
                { name: "pH", symbol: { fill: "#3498DB" } },
                { name: "Klor", symbol: { fill: "#9B59B6" } },
                { name: "Bulanıklık", symbol: { fill: "#1ABC9C" } }
              ]}
            />
            
            <VictoryAxis 
              tickFormat={(t) => {
                const pad = (n) => n.toString().padStart(2, '0');
                return `${pad(t.getHours())}:${pad(t.getMinutes())}`;
              }}
              style={{ tickLabels: { fontSize: 10, padding: 5 } }}
            />
            <VictoryAxis dependentAxis 
              style={{ tickLabels: { fontSize: 10, padding: 5 } }}
            />

            <VictoryLine
              data={phData}
              style={{ data: { stroke: "#3498DB", strokeWidth: 2 } }}
            />
            <VictoryLine
              data={klorData}
              style={{ data: { stroke: "#9B59B6", strokeWidth: 2 } }}
            />
            <VictoryLine
              data={bulaniklikData}
              style={{ data: { stroke: "#1ABC9C", strokeWidth: 2 } }}
            />

            {forecastData.length > 0 && (
              <VictoryLine
                data={forecastData}
                style={{ 
                  data: { 
                    stroke: forecastColor, 
                    strokeWidth: 2,
                    strokeDasharray: "5,5" 
                  } 
                }}
              />
            )}
          </VictoryChart>
        </View>

        <View style={[styles.trendCard, { borderLeftColor: forecastColor, borderLeftWidth: 4 }]}>
          <Text style={styles.trendTitle}>Yapay Zeka Trend Analizi</Text>
          <Text style={styles.trendDesc}>{trendMessage}</Text>
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
  trendScore: { fontSize: 13, color: '#777', marginTop: 8 }
});
