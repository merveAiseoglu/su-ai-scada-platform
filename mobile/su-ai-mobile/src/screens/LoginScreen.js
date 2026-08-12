// screens/LoginScreen.js
// Faz 2 — Kurumsal SCADA Giriş Ekranı

import React, { useState } from "react";
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  KeyboardAvoidingView, Platform, ActivityIndicator, Alert, Image
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { MaterialCommunityIcons } from "@expo/vector-icons";
import { login } from "../services/api";
import { AuthContext } from "../context/AuthContext";

export default function LoginScreen() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [yukleniyor, setYukleniyor] = useState(false);
  const [sifreGizli, setSifreGizli] = useState(true);
  
  const { setIsLoggedIn } = React.useContext(AuthContext);

  const handleLogin = async () => {
    if (!email || !password) {
      Alert.alert("Hata", "Lütfen e-posta ve şifrenizi girin.");
      return;
    }

    setYukleniyor(true);
    try {
      await login(email.trim(), password);
      setIsLoggedIn(true);
    } catch (e) {
      Alert.alert("Giriş Başarısız", e.message);
    } finally {
      setYukleniyor(false);
    }
  };

  const autoFill = (mail, pass) => {
    setEmail(mail);
    setPassword(pass);
  };

  return (
    <SafeAreaView style={styles.container}>
      <KeyboardAvoidingView
        style={styles.keyboardView}
        behavior={Platform.OS === "ios" ? "padding" : "height"}
      >
        {/* Logo ve Başlık Alanı */}
        <View style={styles.header}>
          <MaterialCommunityIcons name="water-circle" size={80} color="#0056b3" />
          <Text style={styles.title}>Su-AI</Text>
          <Text style={styles.subtitle}>Akıllı SCADA Karar Destek Sistemi</Text>
        </View>

        {/* Form Alanı */}
        <View style={styles.formKutu}>
          <Text style={styles.formBaslik}>Sisteme Giriş</Text>
          
          <View style={styles.inputContainer}>
            <MaterialCommunityIcons name="email-outline" size={20} color="#888" style={styles.inputIkon} />
            <TextInput
              style={styles.input}
              placeholder="E-posta Adresi"
              value={email}
              onChangeText={setEmail}
              keyboardType="email-address"
              autoCapitalize="none"
              placeholderTextColor="#AAA"
            />
          </View>

          <View style={styles.inputContainer}>
            <MaterialCommunityIcons name="lock-outline" size={20} color="#888" style={styles.inputIkon} />
            <TextInput
              style={styles.input}
              placeholder="Şifre"
              value={password}
              onChangeText={setPassword}
              secureTextEntry={sifreGizli}
              autoCapitalize="none"
              placeholderTextColor="#AAA"
            />
            <TouchableOpacity onPress={() => setSifreGizli(!sifreGizli)} style={styles.gozBtn}>
              <MaterialCommunityIcons name={sifreGizli ? "eye-off-outline" : "eye-outline"} size={20} color="#888" />
            </TouchableOpacity>
          </View>

          <TouchableOpacity style={styles.loginBtn} onPress={handleLogin} disabled={yukleniyor}>
            {yukleniyor ? (
              <ActivityIndicator color="#FFF" />
            ) : (
              <Text style={styles.loginBtnText}>Giriş Yap</Text>
            )}
          </TouchableOpacity>
        </View>

        {/* Mülakat / Test İçin Hızlı Giriş İpuçları */}
        <View style={styles.testKutu}>
          <Text style={styles.testBaslik}>Test Hesapları (Tek Tıkla Doldur)</Text>
          
          <TouchableOpacity style={styles.testSatir} onPress={() => autoFill("admin@suski.gov.tr", "admin123")}>
            <View style={[styles.rolBadge, { backgroundColor: "#F39C12" }]}>
              <Text style={styles.rolText}>YÖNETİCİ</Text>
            </View>
            <Text style={styles.testEmail}>admin@suski.gov.tr</Text>
          </TouchableOpacity>

          <TouchableOpacity style={styles.testSatir} onPress={() => autoFill("personel1@suski.gov.tr", "pers123")}>
            <View style={[styles.rolBadge, { backgroundColor: "#27AE60" }]}>
              <Text style={styles.rolText}>SAHA PERSONELİ</Text>
            </View>
            <Text style={styles.testEmail}>personel1@suski.gov.tr</Text>
          </TouchableOpacity>
        </View>

      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#0A1628" },
  keyboardView: { flex: 1, justifyContent: "center", padding: 20 },
  header: { alignItems: "center", marginBottom: 40 },
  title: { fontSize: 36, fontWeight: "900", color: "#FFF", letterSpacing: 2, marginTop: 10 },
  subtitle: { fontSize: 14, color: "#00D4FF", marginTop: 4, letterSpacing: 0.5 },
  
  formKutu: {
    backgroundColor: "#FFFFFF",
    borderRadius: 16,
    padding: 24,
    elevation: 8,
    shadowColor: "#000", shadowOffset: { width: 0, height: 4 }, shadowOpacity: 0.2, shadowRadius: 10,
  },
  formBaslik: { fontSize: 20, fontWeight: "700", color: "#1A1A2E", marginBottom: 20, textAlign: "center" },
  
  inputContainer: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#F8F9FA",
    borderWidth: 1,
    borderColor: "#E9ECEF",
    borderRadius: 8,
    marginBottom: 16,
    paddingHorizontal: 12,
    height: 50,
  },
  inputIkon: { marginRight: 10 },
  input: { flex: 1, fontSize: 15, color: "#333" },
  gozBtn: { padding: 4 },
  
  loginBtn: {
    backgroundColor: "#0056b3",
    borderRadius: 8,
    height: 50,
    justifyContent: "center",
    alignItems: "center",
    marginTop: 10,
  },
  loginBtnText: { color: "#FFF", fontSize: 16, fontWeight: "700" },
  
  testKutu: {
    marginTop: 30,
    backgroundColor: "rgba(255,255,255,0.05)",
    padding: 16,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.1)",
  },
  testBaslik: { color: "#AAA", fontSize: 12, fontWeight: "600", marginBottom: 12, textAlign: "center" },
  testSatir: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "rgba(255,255,255,0.1)",
    padding: 10,
    borderRadius: 8,
    marginBottom: 8,
  },
  rolBadge: { paddingHorizontal: 6, paddingVertical: 3, borderRadius: 4, width: 110, alignItems: "center", marginRight: 10 },
  rolText: { color: "#FFF", fontSize: 10, fontWeight: "bold" },
  testEmail: { color: "#FFF", fontSize: 13, flex: 1 },
});
