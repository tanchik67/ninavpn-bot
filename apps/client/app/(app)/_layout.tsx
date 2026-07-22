import { Stack, Redirect } from "expo-router";
import { ActivityIndicator, Platform, View } from "react-native";
import { useAuth } from "../../src/lib/auth";
import { colors } from "../../src/lib/theme";

export default function AppLayout() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <View
        style={{
          flex: 1,
          justifyContent: "center",
          alignItems: "center",
          backgroundColor: colors.bg,
        }}
      >
        <ActivityIndicator color={colors.accent} />
      </View>
    );
  }
  if (!user) return <Redirect href="/(auth)/welcome" />;

  return (
    <Stack
      screenOptions={{
        headerShown: false,
        contentStyle: { backgroundColor: colors.bg },
        // Smooth push/pop for Settings → Language, Profile → Account, etc.
        animation: Platform.OS === "web" ? "fade" : "slide_from_right",
        animationDuration: 420,
        gestureEnabled: true,
        fullScreenGestureEnabled: true,
        animationTypeForReplace: "push",
      }}
    >
      <Stack.Screen name="(tabs)" options={{ animation: "fade", animationDuration: 280 }} />
      <Stack.Screen name="account" />
      <Stack.Screen name="change-password" />
      <Stack.Screen name="config" />
      <Stack.Screen name="language" />
      <Stack.Screen name="text-size" />
      <Stack.Screen name="support" />
      <Stack.Screen name="support-chat" />
      <Stack.Screen name="admin-inbox" />
      <Stack.Screen name="pay" />
      <Stack.Screen name="plans" />
      <Stack.Screen name="subscription" />
    </Stack>
  );
}
