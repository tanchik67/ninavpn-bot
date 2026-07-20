import { BlurView } from "expo-blur";
import { ReactNode } from "react";
import { Platform, StyleSheet, View, ViewStyle } from "react-native";
import { colors, materials, radii } from "../lib/theme";

type Props = {
  children: ReactNode;
  style?: ViewStyle;
  intensity?: number;
  padded?: boolean;
};

/** Primary Liquid Glass surface — blur + hairline specular border. */
export function GlassCard({
  children,
  style,
  intensity = materials.blur,
  padded = true,
}: Props) {
  const pad = padded ? styles.padded : undefined;

  if (Platform.OS === "web") {
    return (
      <View style={[styles.card, styles.webGlass, pad, style]}>{children}</View>
    );
  }

  return (
    <View style={styles.outer}>
      <BlurView intensity={intensity} tint="dark" style={[styles.card, pad, style]}>
        {children}
      </BlurView>
    </View>
  );
}

const styles = StyleSheet.create({
  outer: {
    borderRadius: radii.lg,
    overflow: "hidden",
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.glassBorder,
  },
  card: {
    borderRadius: radii.lg,
    overflow: "hidden",
    backgroundColor: colors.glassFill,
  },
  padded: {
    padding: 16,
  },
  webGlass: {
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.glassBorder,
    backgroundColor: "rgba(17,17,32,0.72)",
    backdropFilter: "blur(24px)",
  } as any,
});
