import { Stack, Redirect } from "expo-router";
import { useEffect } from "react";
import { Platform } from "react-native";
import { BrandSplash } from "../../src/components/BrandSplash";
import { useAuth } from "../../src/lib/auth";
import {
  startAdminSupportPrefetchLoop,
  stopAdminSupportPrefetchLoop,
} from "../../src/lib/adminSupportPrefetch";
import {
  startSupportChatPrefetchLoop,
  stopSupportChatPrefetchLoop,
} from "../../src/lib/supportChatPrefetch";
import { colors } from "../../src/lib/theme";

function isStaff(role?: string) {
  return role === "admin" || role === "support";
}

export default function AppLayout() {
  const { user, loading } = useAuth();

  // Warm support data as soon as the user is in the app (not only on chat open).
  useEffect(() => {
    if (!user) {
      stopSupportChatPrefetchLoop();
      stopAdminSupportPrefetchLoop();
      return;
    }
    if (isStaff(user.role)) {
      stopSupportChatPrefetchLoop();
      startAdminSupportPrefetchLoop();
      return () => stopAdminSupportPrefetchLoop();
    }
    stopAdminSupportPrefetchLoop();
    startSupportChatPrefetchLoop();
    return () => stopSupportChatPrefetchLoop();
  }, [user?.id, user?.role]);

  if (loading) return <BrandSplash />;
  if (!user) return <Redirect href="/(auth)/welcome" />;

  return (
    <Stack
      // Avoid Android Fabric crash: "No view found for id … ScreenStackFragment"
      detachInactiveScreens={false}
      screenOptions={{
        headerShown: false,
        contentStyle: { backgroundColor: colors.bg },
        // Smooth push/pop for Settings → Language, Profile → Account, etc.
        animation: Platform.OS === "ios" ? "slide_from_right" : "fade_from_bottom",
        animationDuration: Platform.OS === "ios" ? 420 : 380,
        gestureEnabled: true,
        // Full-screen gestures race fragment detach on Android New Arch
        fullScreenGestureEnabled: Platform.OS !== "android",
        animationTypeForReplace: "push",
      }}
    >
      <Stack.Screen name="(tabs)" options={{ animation: "fade", animationDuration: 360 }} />
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
      <Stack.Screen name="referral" />
      <Stack.Screen name="guides" />
      <Stack.Screen name="servers" />
      <Stack.Screen name="faq" />
      <Stack.Screen name="about" />
      <Stack.Screen name="connection-profiles" />
    </Stack>
  );
}
