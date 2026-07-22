import { Stack } from "expo-router";
import { Platform } from "react-native";
import { colors } from "../../src/lib/theme";

export default function AuthLayout() {
  return (
    <Stack
      screenOptions={{
        headerShown: false,
        contentStyle: { backgroundColor: colors.bg },
        animation: Platform.OS === "web" ? "fade" : "slide_from_right",
        animationDuration: 400,
        gestureEnabled: true,
        animationTypeForReplace: "push",
      }}
    />
  );
}
