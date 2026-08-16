import MaskedView from "@react-native-masked-view/masked-view";
import { LinearGradient } from "expo-linear-gradient";
import { Platform, StyleSheet, TextStyle, View } from "react-native";
import { AppText as Text } from "./AppText";
import { colors, fonts } from "../lib/theme";

/** Site wordmark: purple→pink NINA + cyan VPN (matches ninavpn.store). */
export function NinaLogo({ size = 28 }: { size?: number }) {
  const base: TextStyle = {
    fontFamily: fonts.display,
    fontSize: size,
    letterSpacing: -0.8,
    lineHeight: Math.round(size * 1.15),
  };

  const ninaNative = (
    <MaskedView
      style={{ height: Math.round(size * 1.2) }}
      maskElement={
        <View style={styles.maskWrap}>
          <Text style={[base, styles.maskText]}>NINA</Text>
        </View>
      }
    >
      <LinearGradient
        colors={["#7B2FFF", "#FF2FA0"]}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={styles.gradientFill}
      >
        <Text style={[base, { opacity: 0 }]}>NINA</Text>
      </LinearGradient>
    </MaskedView>
  );

  const ninaWeb = (
    <Text
      style={[
        base,
        {
          backgroundImage: "linear-gradient(135deg, #7B2FFF, #FF2FA0)",
          backgroundClip: "text",
          WebkitBackgroundClip: "text",
          color: "transparent",
          WebkitTextFillColor: "transparent",
        } as TextStyle,
      ]}
    >
      NINA
    </Text>
  );

  return (
    <View style={styles.row}>
      {Platform.OS === "web" ? ninaWeb : ninaNative}
      <Text style={[base, { color: colors.accent3 }]}>VPN</Text>
    </View>
  );
}

export function ScreenTitle({ children }: { children: string }) {
  return <Text style={styles.title}>{children}</Text>;
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", alignItems: "center" },
  maskWrap: { backgroundColor: "transparent" },
  maskText: { color: "#000" },
  gradientFill: { flex: 1 },
  title: {
    fontFamily: fonts.displayBold,
    fontSize: 28,
    letterSpacing: -0.5,
    color: colors.text,
    marginBottom: 16,
  },
});
