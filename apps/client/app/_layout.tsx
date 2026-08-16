import {
  Onest_400Regular,
  Onest_500Medium,
  Onest_600SemiBold,
  Onest_700Bold,
} from "@expo-google-fonts/onest";
import {
  Unbounded_400Regular,
  Unbounded_700Bold,
  Unbounded_900Black,
} from "@expo-google-fonts/unbounded";
import { useFonts } from "expo-font";
import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { useEffect } from "react";
import { AppState, StyleSheet } from "react-native";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { BrandSplash } from "../src/components/BrandSplash";
import { AuthProvider } from "../src/lib/auth";
import { attachAutoConnectAppState } from "../src/lib/autoConnect";
import { I18nProvider } from "../src/lib/i18n";
import { ninaVpnEnsureNetwork } from "../src/lib/ninaVpn";
import { TextSizeProvider } from "../src/lib/textSize";

export default function RootLayout() {
  const [fontsLoaded] = useFonts({
    Unbounded_400Regular,
    Unbounded_700Bold,
    Unbounded_900Black,
    Onest_400Regular,
    Onest_500Medium,
    Onest_600SemiBold,
    Onest_700Bold,
  });

  useEffect(() => {
    void ninaVpnEnsureNetwork();
    const stopAuto = attachAutoConnectAppState();
    const sub = AppState.addEventListener("change", (state) => {
      if (state === "active") void ninaVpnEnsureNetwork();
    });
    return () => {
      stopAuto();
      sub.remove();
    };
  }, []);

  if (!fontsLoaded) {
    return <BrandSplash />;
  }

  return (
    <GestureHandlerRootView style={styles.root}>
    <TextSizeProvider>
      <I18nProvider>
        <AuthProvider>
          <StatusBar style="light" />
          <Stack
            detachInactiveScreens={false}
            screenOptions={{
              headerShown: false,
              contentStyle: { backgroundColor: "#000000" },
              animation: "fade",
              animationDuration: 400,
              animationTypeForReplace: "push",
            }}
          >
            <Stack.Screen name="index" />
            <Stack.Screen name="(auth)" />
            <Stack.Screen name="(app)" />
            <Stack.Screen name="google-auth" options={{ animation: "fade" }} />
            <Stack.Screen name="tg-auth" options={{ animation: "fade" }} />
            <Stack.Screen name="+not-found" options={{ animation: "fade" }} />
          </Stack>
        </AuthProvider>
      </I18nProvider>
    </TextSizeProvider>
    </GestureHandlerRootView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "#000000" },
});
