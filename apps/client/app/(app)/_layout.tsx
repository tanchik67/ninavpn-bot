import { Redirect, Tabs } from "expo-router";
import { ActivityIndicator, View } from "react-native";
import { useAuth } from "../../src/lib/auth";
import { colors } from "../../src/lib/theme";

export default function AppLayout() {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <View style={{ flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: colors.bg }}>
        <ActivityIndicator color={colors.accent} />
      </View>
    );
  }
  if (!user) return <Redirect href="/(auth)/login" />;

  return (
    <Tabs
      screenOptions={{
        headerStyle: { backgroundColor: colors.bg },
        headerTintColor: colors.text,
        tabBarStyle: { backgroundColor: colors.surface, borderTopColor: colors.border },
        tabBarActiveTintColor: colors.accent,
        tabBarInactiveTintColor: colors.muted,
      }}
    >
      <Tabs.Screen name="plans" options={{ title: "Тарифы" }} />
      <Tabs.Screen name="subscription" options={{ title: "Подписка" }} />
      <Tabs.Screen name="config" options={{ title: "Конфиг" }} />
      <Tabs.Screen name="support" options={{ title: "Поддержка" }} />
      <Tabs.Screen name="account" options={{ title: "Аккаунт" }} />
      <Tabs.Screen name="pay" options={{ href: null, title: "Оплата" }} />
    </Tabs>
  );
}
