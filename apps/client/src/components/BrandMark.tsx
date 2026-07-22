import { StyleSheet, View } from "react-native";
import { AppText as Text } from "./AppText";
import { colors, fonts } from "../lib/theme";
import { NinaLogo } from "./NinaLogo";

/** Brand wordmark — delegates to NinaLogo (site DNA). */
export function BrandMark({ size = 34 }: { size?: number }) {
  return <NinaLogo size={size} />;
}

export function BrandGradientTitle({ children }: { children: string }) {
  return (
    <View>
      <Text style={styles.gradText}>{children}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  gradText: {
    fontFamily: fonts.display,
    fontSize: 34,
    color: colors.text,
    letterSpacing: -0.8,
  },
});
