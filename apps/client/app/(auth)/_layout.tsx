import { Stack } from "expo-router";
import { Platform } from "react-native";
import { colors } from "../../src/lib/theme";

export default function AuthLayout() {
  return (
    <Stack
      detachInactiveScreens={false}
      screenOptions={{
        headerShown: false,
        contentStyle: { backgroundColor: colors.bg },
        animation: Platform.OS === "ios" ? "slide_from_right" : "fade_from_bottom",
        animationDuration: Platform.OS === "ios" ? 400 : 360,
        gestureEnabled: true,
        animationTypeForReplace: "push",
      }}
    />
  );
}
