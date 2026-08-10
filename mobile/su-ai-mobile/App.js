// App.js
// Su-AI Mobil Uygulaması — Ana Navigator

import React, { useEffect, useState } from "react";
import { NavigationContainer } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { View, ActivityIndicator } from "react-native";
import { StatusBar } from "expo-status-bar";

import IstasyonListesiScreen from "./src/screens/IstasyonListesiScreen";
import MeasurementFormScreen from "./src/screens/MeasurementFormScreen";
import ResultScreen from "./src/screens/ResultScreen";
import MapScreen from "./src/screens/MapScreen";
import StationHistoryScreen from "./src/screens/StationHistoryScreen";
import SimulatorScreen from "./src/screens/SimulatorScreen";
import AuditLogScreen from "./src/screens/AuditLogScreen";
import LoginScreen from "./src/screens/LoginScreen";
import { kanallarOlustur } from "./src/services/notificationService";
import { getToken } from "./src/services/api";

// 1. AuthContext Oluştur
export const AuthContext = React.createContext();

const Stack = createNativeStackNavigator();

export default function App() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [isChecking, setIsChecking] = useState(true);

  useEffect(() => {
    // Android bildirim kanallarını uygulama başlangıcında oluştur
    kanallarOlustur();

    const checkAuth = async () => {
      const token = await getToken();
      setIsLoggedIn(!!token);
      setIsChecking(false);
    };
    checkAuth();
  }, []);

  if (isChecking) {
    return (
      <View style={{ flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: "#0A1628" }}>
        <ActivityIndicator size="large" color="#00D4FF" />
      </View>
    );
  }

  return (
    <AuthContext.Provider value={{ isLoggedIn, setIsLoggedIn }}>
      <NavigationContainer>
        <StatusBar style="light" backgroundColor="#0056b3" />
        <Stack.Navigator screenOptions={{ headerShown: false }}>
          {!isLoggedIn ? (
            <Stack.Screen 
              name="LoginScreen" 
              component={LoginScreen}
            />
          ) : (
            <>
              <Stack.Screen 
                name="IstasyonListesi" 
                component={IstasyonListesiScreen}
              />
            <Stack.Screen
              name="MeasurementForm"
              component={MeasurementFormScreen}
              options={{ animation: "slide_from_right" }}
            />
            <Stack.Screen
              name="ResultScreen"
              component={ResultScreen}
              options={{ animation: "fade" }}
            />
            <Stack.Screen
              name="MapScreen"
              component={MapScreen}
              options={{ animation: "slide_from_right" }}
            />
            <Stack.Screen
              name="StationHistoryScreen"
              component={StationHistoryScreen}
              options={{ animation: "slide_from_right" }}
            />
            <Stack.Screen
              name="SimulatorScreen"
              component={SimulatorScreen}
              options={{ animation: "slide_from_bottom" }}
            />
            <Stack.Screen
              name="AuditLogScreen"
              component={AuditLogScreen}
              options={{ animation: "slide_from_bottom" }}
            />
          </>
        )}
      </Stack.Navigator>
    </NavigationContainer>
    </AuthContext.Provider>
  );
}
