import { LinearGradient } from "expo-linear-gradient";
import { ReactNode } from "react";
import { StyleSheet, View, ViewStyle } from "react-native";
import { colors, gradients } from "../lib/theme";

type Props = { children: ReactNode; style?: ViewStyle };

export function ScreenBackground({ children, style }: Props) {
  return (
    <View style={[styles.root, style]}>
      <LinearGradient colors={[...gradients.screen]} style={StyleSheet.absoluteFill} />
      <View style={styles.ambient} pointerEvents="none" />
      <View style={styles.content}>{children}</View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  content: { flex: 1 },
  ambient: {
    position: "absolute",
    top: -120,
    alignSelf: "center",
    left: "15%",
    width: "70%",
    height: 280,
    borderRadius: 200,
    backgroundColor: colors.accentGlow,
    opacity: 0.85,
  },
});
