import { BlurView } from "expo-blur";
import { Tabs, usePathname } from "expo-router";
import type { BottomTabBarButtonProps } from "@react-navigation/bottom-tabs";
import {
  Platform,
  Pressable,
  StyleSheet,
  Text,
  useWindowDimensions,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useT } from "../../../src/lib/i18n";
import { getDockHeight, useFontScale } from "../../../src/lib/textSize";
import { colors, fonts } from "../../../src/lib/theme";

/** Inactive label — light enough to stay visible on dark dock */
const LABEL_IDLE = "rgba(240,238,255,0.78)";
const EMOJI_IDLE = 0.75;

type TabKey = "home" | "profile" | "settings";

function TabItem({
  emoji,
  label,
  focused,
  scale,
  landscape,
}: {
  emoji: string;
  label: string;
  focused: boolean;
  scale: number;
  landscape: boolean;
}) {
  const iconSize = Math.round(22 * Math.min(Math.max(scale, 1), 1.45));
  const labelSize = Math.round(10 * scale * 10) / 10;
  const gap = landscape
    ? Math.max(6, Math.round(6 * scale))
    : Math.max(4, Math.round(4 * scale));

  return (
    <View
      style={[
        styles.tabItemInner,
        landscape ? styles.tabItemRow : styles.tabItemCol,
        { gap },
      ]}
      pointerEvents="none"
    >
      <Text
        style={{
          fontSize: iconSize,
          lineHeight: iconSize + 4,
          opacity: focused ? 1 : EMOJI_IDLE,
          fontFamily: Platform.select({
            ios: "System",
            android: "sans-serif",
            default: undefined,
          }),
          textAlign: "center",
          includeFontPadding: false,
        }}
      >
        {emoji}
      </Text>
      <Text
        style={{
          fontFamily: fonts.bodySemi,
          fontSize: labelSize,
          lineHeight: Math.round(labelSize * 1.25),
          color: focused ? colors.accent : LABEL_IDLE,
          textAlign: landscape ? "left" : "center",
          includeFontPadding: false,
          flexShrink: 0,
        }}
      >
        {label}
      </Text>
    </View>
  );
}

function DockBackground({ radius }: { radius: number }) {
  if (Platform.OS === "web") {
    return <View style={[styles.dockBgWeb, { borderRadius: radius }]} />;
  }
  return (
    <View style={[styles.dockOuter, { borderRadius: radius }]}>
      <BlurView intensity={55} tint="dark" style={StyleSheet.absoluteFill} />
      <View style={styles.dockTint} />
    </View>
  );
}

function TabButton({
  emoji,
  label,
  tabKey,
  scale,
  landscape,
  accessibilityState,
  onPress,
  onLongPress,
  style,
}: BottomTabBarButtonProps & {
  emoji: string;
  label: string;
  tabKey: TabKey;
  scale: number;
  landscape: boolean;
}) {
  const pathname = usePathname();
  const focused =
    pathname === `/${tabKey}` ||
    pathname.endsWith(`/${tabKey}`) ||
    !!accessibilityState?.selected;

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ ...accessibilityState, selected: focused }}
      onPress={onPress}
      onLongPress={onLongPress}
      style={[style, styles.tabButton]}
    >
      <TabItem
        emoji={emoji}
        label={label}
        focused={focused}
        scale={scale}
        landscape={landscape}
      />
    </Pressable>
  );
}

export default function TabsLayout() {
  const t = useT();
  const scale = useFontScale();
  const insets = useSafeAreaInsets();
  const { width, height } = useWindowDimensions();
  const landscape = width > height;

  const bottomPad = Math.max(insets.bottom, 12);
  const dockHeight = landscape
    ? Math.max(56, Math.round(getDockHeight(scale) * 0.72))
    : getDockHeight(scale);
  const dockRadius = Math.min(36, Math.round(dockHeight / 2.3));

  const homeLabel = t("tabs.home");
  const profileLabel = t("tabs.profile");
  const settingsLabel = t("tabs.settings");

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        sceneStyle: { backgroundColor: colors.bg },
        tabBarActiveTintColor: colors.accent,
        tabBarInactiveTintColor: LABEL_IDLE,
        tabBarShowLabel: false,
        // Soft cross-fade / shift between Home · Profile · Settings
        animation: Platform.OS === "web" ? "fade" : "shift",
        tabBarStyle: [
          styles.tabBar,
          {
            bottom: bottomPad,
            height: dockHeight,
            borderRadius: dockRadius,
            paddingTop: 0,
            paddingBottom: 0,
          },
        ],
        tabBarItemStyle: {
          flex: 1,
          height: dockHeight,
          justifyContent: "center",
          alignItems: "center",
          paddingVertical: 0,
          paddingHorizontal: 2,
        },
        tabBarBackground: () => <DockBackground radius={dockRadius} />,
      }}
    >
      <Tabs.Screen
        name="home"
        options={{
          title: homeLabel,
          tabBarIcon: () => null,
          tabBarButton: (props) => (
            <TabButton
              {...props}
              emoji="🏠"
              label={homeLabel}
              tabKey="home"
              scale={scale}
              landscape={landscape}
            />
          ),
        }}
      />
      <Tabs.Screen
        name="profile"
        options={{
          title: profileLabel,
          tabBarIcon: () => null,
          tabBarButton: (props) => (
            <TabButton
              {...props}
              emoji="👤"
              label={profileLabel}
              tabKey="profile"
              scale={scale}
              landscape={landscape}
            />
          ),
        }}
      />
      <Tabs.Screen
        name="settings"
        options={{
          title: settingsLabel,
          tabBarIcon: () => null,
          tabBarButton: (props) => (
            <TabButton
              {...props}
              emoji="⚙️"
              label={settingsLabel}
              tabKey="settings"
              scale={scale}
              landscape={landscape}
            />
          ),
        }}
      />
    </Tabs>
  );
}

const DOCK_RADIUS = 28;

const styles = StyleSheet.create({
  tabButton: {
    flex: 1,
    height: "100%",
    justifyContent: "center",
    alignItems: "center",
    overflow: "visible",
  },
  tabItemInner: {
    alignItems: "center",
    justifyContent: "center",
    maxWidth: "100%",
    paddingHorizontal: 2,
  },
  tabItemCol: {
    flexDirection: "column",
  },
  tabItemRow: {
    flexDirection: "row",
  },
  tabBar: {
    position: "absolute",
    left: 20,
    right: 20,
    borderRadius: DOCK_RADIUS,
    borderTopWidth: 0,
    borderTopColor: "transparent",
    borderWidth: 0,
    backgroundColor: "transparent",
    elevation: 0,
    shadowColor: "#000",
    shadowOpacity: 0.35,
    shadowRadius: 20,
    shadowOffset: { width: 0, height: 8 },
    overflow: "visible",
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
});
