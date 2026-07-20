import { BlurView } from "expo-blur";
import { Redirect, Tabs } from "expo-router";
import { Platform, StyleSheet, Text, View } from "react-native";
import { ActivityIndicator } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useAuth } from "../../src/lib/auth";
import { colors, fonts } from "../../src/lib/theme";

function TabIcon({ emoji, focused }: { emoji: string; focused: boolean }) {
  return (
    <Text
      style={{
        fontSize: 22,
        opacity: focused ? 1 : 0.55,
        fontFamily: Platform.select({
          ios: "System",
          android: "sans-serif",
          default: undefined,
        }),
      }}
    >
      {emoji}
    </Text>
  );
}

function DockBackground() {
  if (Platform.OS === "web") {
    return <View style={styles.dockBgWeb} />;
  }
  return (
    <View style={styles.dockOuter}>
      <BlurView intensity={55} tint="dark" style={StyleSheet.absoluteFill} />
      <View style={styles.dockTint} />
    </View>
  );
}

export default function AppLayout() {
  const { user, loading } = useAuth();
  const insets = useSafeAreaInsets();

  if (loading) {
    return (
      <View style={styles.loader}>
        <ActivityIndicator color={colors.accent} />
      </View>
    );
  }
  if (!user) return <Redirect href="/(auth)/welcome" />;

  const bottomPad = Math.max(insets.bottom, 12);

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        sceneStyle: { backgroundColor: colors.bg },
        tabBarActiveTintColor: colors.accent,
        tabBarInactiveTintColor: colors.muted,
        tabBarLabelStyle: styles.tabLabel,
        tabBarShowLabel: true,
        tabBarStyle: [
          styles.tabBar,
          {
            bottom: bottomPad,
          },
        ],
        tabBarItemStyle: styles.tabItem,
        tabBarBackground: () => <DockBackground />,
      }}
    >
      <Tabs.Screen
        name="home"
        options={{
          title: "Главная",
          tabBarIcon: ({ focused }) => <TabIcon emoji="🏠" focused={focused} />,
        }}
      />
      <Tabs.Screen
        name="profile"
        options={{
          title: "Профиль",
          tabBarIcon: ({ focused }) => <TabIcon emoji="👤" focused={focused} />,
        }}
      />
      <Tabs.Screen
        name="settings"
        options={{
          title: "Настройки",
          tabBarIcon: ({ focused }) => <TabIcon emoji="⚙️" focused={focused} />,
        }}
      />
      <Tabs.Screen name="account" options={{ href: null }} />
      <Tabs.Screen name="config" options={{ href: null }} />
      <Tabs.Screen name="support" options={{ href: null }} />
      <Tabs.Screen name="support-chat" options={{ href: null }} />
      <Tabs.Screen name="pay" options={{ href: null }} />
      <Tabs.Screen name="plans" options={{ href: null }} />
      <Tabs.Screen name="subscription" options={{ href: null }} />
    </Tabs>
  );
}

const DOCK_RADIUS = 28;

const styles = StyleSheet.create({
  loader: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: colors.bg,
  },
  tabBar: {
    position: "absolute",
    left: 20,
    right: 20,
    height: 68,
    borderRadius: DOCK_RADIUS,
    // Kill default React Navigation top hairline (white stripe)
    borderTopWidth: 0,
    borderTopColor: "transparent",
    borderWidth: 0,
    backgroundColor: "transparent",
    elevation: 0,
    shadowColor: "#000",
    shadowOpacity: 0.35,
    shadowRadius: 20,
    shadowOffset: { width: 0, height: 8 },
    paddingBottom: 6,
    paddingTop: 6,
    overflow: "hidden",
  },
  tabItem: {
    paddingVertical: 2,
  },
  dockOuter: {
    ...StyleSheet.absoluteFillObject,
    borderRadius: DOCK_RADIUS,
    overflow: "hidden",
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: "rgba(255,255,255,0.12)",
  },
  dockTint: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(20,18,32,0.55)",
  },
  dockBgWeb: {
    ...StyleSheet.absoluteFillObject,
    borderRadius: DOCK_RADIUS,
    backgroundColor: "rgba(22,20,36,0.78)",
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: "rgba(255,255,255,0.12)",
    backdropFilter: "blur(28px)",
    WebkitBackdropFilter: "blur(28px)",
  } as any,
  tabLabel: {
    fontFamily: fonts.bodySemi,
    fontSize: 10,
    marginTop: 2,
  },
});
