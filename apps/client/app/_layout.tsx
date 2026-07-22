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
import { ActivityIndicator, View } from "react-native";
import { AuthProvider } from "../src/lib/auth";
import { I18nProvider } from "../src/lib/i18n";
import { TextSizeProvider } from "../src/lib/textSize";
import { colors } from "../src/lib/theme";

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

  if (!fontsLoaded) {
    return (
      <View
        style={{
          flex: 1,
          backgroundColor: colors.bg,
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <ActivityIndicator color={colors.accent} />
      </View>
    );
  }

  return (
    <TextSizeProvider>
      <I18nProvider>
        <AuthProvider>
          <StatusBar style="light" />
          <Stack
            screenOptions={{
              headerShown: false,
              contentStyle: { backgroundColor: colors.bg },
              animation: "fade",
              animationDuration: 360,
              animationTypeForReplace: "push",
            }}
          >
            <Stack.Screen name="index" />
            <Stack.Screen name="(auth)" />
            <Stack.Screen name="(app)" />
          </Stack>
        </AuthProvider>
      </I18nProvider>
    </TextSizeProvider>
  );
}
