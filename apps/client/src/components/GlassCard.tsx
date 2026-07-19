import { BlurView } from "expo-blur";
import { ReactNode } from "react";
import { Platform, StyleSheet, View, ViewStyle } from "react-native";
import { colors, radii } from "../lib/theme";

type Props = {
  children: ReactNode;
  style?: ViewStyle;
  intensity?: number;
};

export function GlassCard({ children, style, intensity = 40 }: Props) {
  if (Platform.OS === "web") {
    return <View style={[styles.card, styles.webGlass, style]}>{children}</View>;
  }
  return (
    <BlurView intensity={intensity} tint="dark" style={[styles.card, style]}>
      {children}
    </BlurView>
  );
}

const styles = StyleSheet.create({
  card: {
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: colors.glassBorder,
    overflow: "hidden",
    padding: 16,
  },
  webGlass: {
    backgroundColor: "rgba(255,255,255,0.1)",
    backdropFilter: "blur(20px)" as any,
  },
});
