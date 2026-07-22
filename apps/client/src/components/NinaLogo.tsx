import { Platform, StyleSheet, TextStyle, View } from "react-native";
import { AppText as Text } from "./AppText";
import { colors, fonts } from "../lib/theme";

/** Site wordmark: gradient NINA + cyan VPN. */
export function NinaLogo({ size = 28 }: { size?: number }) {
  const webGradient: TextStyle =
    Platform.OS === "web"
      ? ({
          backgroundImage: "linear-gradient(135deg, #7B2FFF, #FF2FA0)",
          backgroundClip: "text",
          WebkitBackgroundClip: "text",
          color: "transparent",
          WebkitTextFillColor: "transparent",
        } as TextStyle)
      : { color: colors.accent };

  return (
    <View style={styles.row}>
      <Text style={[styles.nina, { fontSize: size }, webGradient]}>NINA</Text>
      <Text style={[styles.vpn, { fontSize: size }]}>VPN</Text>
    </View>
  );
}

export function ScreenTitle({ children }: { children: string }) {
  return <Text style={styles.title}>{children}</Text>;
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", alignItems: "baseline" },
  nina: {
    fontFamily: fonts.display,
    letterSpacing: -0.8,
  },
  vpn: {
    fontFamily: fonts.display,
    letterSpacing: -0.8,
    color: colors.accent3,
  },
  title: {
    fontFamily: fonts.displayBold,
    fontSize: 28,
    letterSpacing: -0.5,
    color: colors.text,
    marginBottom: 16,
  },
});
