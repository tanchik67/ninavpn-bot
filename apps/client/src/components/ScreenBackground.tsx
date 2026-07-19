import { LinearGradient } from "expo-linear-gradient";
import { ReactNode } from "react";
import { StyleSheet, View, ViewStyle } from "react-native";
import { colors, gradients } from "../lib/theme";

type Props = {
  children: ReactNode;
  style?: ViewStyle;
};

/** Dark nebula backdrop matching NINAVPN mockups. */
export function ScreenBackground({ children, style }: Props) {
  return (
    <View style={[styles.root, style]}>
      <LinearGradient colors={[...gradients.nebula]} style={StyleSheet.absoluteFill} />
      <View style={[styles.blob, styles.blobPink]} />
      <View style={[styles.blob, styles.blobTeal]} />
      <View style={[styles.blob, styles.blobPurple]} />
      <View style={styles.content}>{children}</View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  content: { flex: 1 },
  blob: {
    position: "absolute",
    borderRadius: 999,
    opacity: 0.45,
  },
  blobPink: {
    width: 280,
    height: 280,
    top: -60,
    right: -80,
    backgroundColor: "#DB2777",
  },
  blobTeal: {
    width: 220,
    height: 220,
    bottom: 120,
    left: -70,
    backgroundColor: "#0D9488",
  },
  blobPurple: {
    width: 180,
    height: 180,
    top: "40%",
    right: -40,
    backgroundColor: "#7C3AED",
  },
});
