import { Redirect, Tabs } from "expo-router";
import { ActivityIndicator, Text, View } from "react-native";
import { useAuth } from "../../src/lib/auth";
import { colors } from "../../src/lib/theme";

function TabLabel({ label, focused }: { label: string; focused: boolean }) {
  return (
    <Text style={{ color: focused ? colors.accentPink : colors.muted, fontSize: 11, fontWeight: "700" }}>
      {label}
    </Text>
  );
}

export default function AppLayout() {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <View style={{ flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: colors.bg }}>
        <ActivityIndicator color={colors.accentPink} />
      </View>
    );
  }
  if (!user) return <Redirect href="/(auth)/login" />;

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarStyle: {
          backgroundColor: "rgba(7,7,26,0.96)",
          borderTopColor: colors.glassBorder,
          borderTopWidth: 1,
          height: 64,
          paddingBottom: 8,
          paddingTop: 8,
        },
        tabBarActiveTintColor: colors.accentPink,
        tabBarInactiveTintColor: colors.muted,
      }}
    >
      <Tabs.Screen
        name="home"
        options={{
          title: "Home",
          tabBarLabel: ({ focused }) => <TabLabel label="Home" focused={focused} />,
        }}
      />
      <Tabs.Screen
        name="plans"
        options={{
          title: "Plans",
          tabBarLabel: ({ focused }) => <TabLabel label="Plans" focused={focused} />,
        }}
      />
      <Tabs.Screen
        name="subscription"
        options={{
          title: "Status",
          tabBarLabel: ({ focused }) => <TabLabel label="Status" focused={focused} />,
        }}
      />
      <Tabs.Screen
        name="account"
        options={{
          title: "Settings",
          tabBarLabel: ({ focused }) => <TabLabel label="Settings" focused={focused} />,
        }}
      />
      <Tabs.Screen name="config" options={{ href: null }} />
      <Tabs.Screen name="support" options={{ href: null }} />
      <Tabs.Screen name="pay" options={{ href: null }} />
    </Tabs>
  );
}
