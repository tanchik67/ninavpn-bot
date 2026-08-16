import { BlurView } from "expo-blur";
import { ReactNode } from "react";
import { Platform, StyleSheet, View, ViewStyle, StyleProp } from "react-native";
import { colors, materials, radii } from "../lib/theme";

type Props = {
  children: ReactNode;
  style?: StyleProp<ViewStyle>;
  intensity?: number;
  padded?: boolean;
  clip?: boolean;
  radius?: number;
};

/** Primary Liquid Glass surface — blur + hairline specular border. */
export function GlassCard({
  children,
  style,
  intensity = materials.blur,
  padded = true,
  clip = true,
  radius = radii.lg,
}: Props) {
  const pad = padded ? styles.padded : undefined;
  const clipStyle = clip ? styles.clip : styles.noClip;
  const round = { borderRadius: radius };

  if (Platform.OS === "web") {
    return (
      <View style={[styles.outer, styles.webGlass, round, pad, clipStyle, style]}>{children}</View>
    );
  }

  // Apply caller layout (margin/padding/align) on the bordered box so the
  // purple hairline hugs the rectangle — not a child margin inside it.
  return (
    <View style={[styles.outer, round, pad, clipStyle, style]}>
      <View
        style={[StyleSheet.absoluteFill, styles.clip, round]}
        pointerEvents="none"
      >
        <BlurView
          intensity={intensity}
          tint="dark"
          style={[StyleSheet.absoluteFill, round]}
          pointerEvents="none"
        />
      </View>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  outer: {
    borderRadius: radii.lg,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.glassBorder,
    backgroundColor: colors.glassFill,
  },
  clip: {
    overflow: "hidden",
  },
  noClip: {
    overflow: "visible",
  },
  padded: {
    padding: 16,
  },
  webGlass: {
    backgroundColor: "rgba(17,17,32,0.72)",
    backdropFilter: "blur(24px)",
  } as any,
});
