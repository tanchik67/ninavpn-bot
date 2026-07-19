import { StyleSheet, Text } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { gradients } from "../lib/theme";

/** Brand wordmark like the mockup. */
export function BrandMark({ size = 34 }: { size?: number }) {
  return (
    <Text style={[styles.brand, { fontSize: size }]}>
      NINA
      <Text style={styles.vpn}>VPN</Text>
    </Text>
  );
}

export function BrandGradientTitle({ children }: { children: string }) {
  return (
    <LinearGradient
      colors={[...gradients.brand]}
      start={{ x: 0, y: 0 }}
      end={{ x: 1, y: 0 }}
      style={styles.gradWrap}
    >
      <Text style={styles.gradText}>{children}</Text>
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  brand: {
    fontWeight: "900",
    letterSpacing: -1,
    color: "#fff",
  },
  vpn: {
    color: "#F472B6",
  },
  gradWrap: {
    alignSelf: "flex-start",
    borderRadius: 8,
    paddingHorizontal: 2,
  },
  gradText: {
    fontSize: 36,
    fontWeight: "900",
    color: "#fff",
    letterSpacing: -1,
  },
});
