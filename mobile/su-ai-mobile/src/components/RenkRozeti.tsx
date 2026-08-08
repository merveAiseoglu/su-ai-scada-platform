import React from 'react';
import { View, Text, StyleSheet } from 'react-native';

const RISK_RENKLERI = {
  NORMAL: { bg: '#E8F5E9', text: '#28A745' }, // Yeşil
  DÜŞÜK: { bg: '#FFF8E1', text: '#FFC107' }, // Sarı
  ORTA: { bg: '#FFF3E0', text: '#FD7E14' },  // Turuncu
  KRİTİK: { bg: '#FFEBEE', text: '#DC3545' }, // Kırmızı
};

type RiskSeviyesi = keyof typeof RISK_RENKLERI;

export default function RenkRozeti({ riskSeviyesi }: { riskSeviyesi: RiskSeviyesi }) {
  const renk = RISK_RENKLERI[riskSeviyesi] || RISK_RENKLERI['NORMAL'];

  return (
    <View style={[styles.badge, { backgroundColor: renk.bg }]}>
      <Text style={[styles.badgeText, { color: renk.text }]}>{riskSeviyesi}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 8,
    alignSelf: 'center',
    borderWidth: 1,
    borderColor: 'rgba(0,0,0,0.05)',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.1,
    shadowRadius: 2,
    elevation: 2,
  },
  badgeText: {
    fontSize: 16,
    fontWeight: '800',
    letterSpacing: 0.5,
  },
});
