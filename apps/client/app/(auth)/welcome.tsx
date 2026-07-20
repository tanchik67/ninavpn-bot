import { router } from "expo-router";
import { StyleSheet, Text, View } from "react-native";
import { NinaLogo } from "../../src/components/NinaLogo";
import { PrimaryButton } from "../../src/components/PrimaryButton";
import { ScreenBackground } from "../../src/components/ScreenBackground";
import { colors, fonts, spacing } from "../../src/lib/theme";

export default function WelcomeScreen() {
  return (
    <ScreenBackground>
      <View style={styles.wrap}>
        <View style={styles.top}>
          <NinaLogo size={36} />
          <Text style={styles.title}>Интернет{"\n"}без цензуры</Text>
          <Text style={styles.sub}>Кабинет NinaVPN — спокойно, быстро, без лишнего</Text>
        </View>
        <PrimaryButton label="Начать" onPress={() => router.push("/(auth)/login")} />
      </View>
    </ScreenBackground>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flex: 1,
    paddingHorizontal: spacing.xl,
    paddingTop: 80,
    paddingBottom: 48,
    justifyContent: "space-between",
  },
  top: { gap: spacing.md },
  title: {
    fontFamily: fonts.display,
    fontSize: 40,
    lineHeight: 46,
    letterSpacing: -1,
    color: colors.text,
    marginTop: spacing.xxl,
  },
  sub: {
    fontFamily: fonts.body,
    fontSize: 16,
    lineHeight: 22,
    color: colors.muted,
    maxWidth: 280,
  },
});
