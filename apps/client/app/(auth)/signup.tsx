import { Link, router } from "expo-router";
import { useState } from "react";
import { Pressable, StyleSheet, View } from "react-native";
import { AppText as Text } from "../../src/components/AppText";
import { NinaLogo } from "../../src/components/NinaLogo";
import { PrimaryButton } from "../../src/components/PrimaryButton";
import { ScreenBackground } from "../../src/components/ScreenBackground";
import { SocialAuthButtons } from "../../src/components/SocialAuthButtons";
import { useI18n } from "../../src/lib/i18n";
import { colors, fonts, spacing } from "../../src/lib/theme";

export default function SignupScreen() {
  const { t } = useI18n();
  const [error, setError] = useState("");

  return (
    <ScreenBackground>
      <View style={styles.wrap}>
        <Pressable onPress={() => router.back()} hitSlop={12} style={styles.back}>
          <Text style={styles.backText}>{t("common.back")}</Text>
        </Pressable>

        <NinaLogo size={28} />
        <Text
          style={styles.headline}
          numberOfLines={1}
          adjustsFontSizeToFit
          minimumFontScale={0.72}
        >
          {t("welcome.register")}
        </Text>
        <Text style={styles.sub}>{t("signup.subtitle")}</Text>

        {!!error && <Text style={styles.error}>{error}</Text>}

        <SocialAuthButtons
          showDivider={false}
          googleLabel={t("welcome.viaGoogle")}
          telegramLabel={t("welcome.viaTelegram")}
          onSuccess={() => router.replace("/(app)/(tabs)/home")}
          onError={setError}
        />

        <PrimaryButton
          label={t("welcome.viaEmail")}
          onPress={() => router.push("/(auth)/register")}
          style={{ marginTop: 4 }}
        />

        <Link href="/(auth)/login" style={styles.link}>
          {t("register.haveAccount")}
        </Link>
      </View>
    </ScreenBackground>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flex: 1,
    paddingHorizontal: spacing.xl,
    paddingTop: 56,
    paddingBottom: 48,
    justifyContent: "center",
    gap: 8,
  },
  back: {
    position: "absolute",
    top: 52,
    left: spacing.xl,
    zIndex: 1,
  },
  backText: {
    color: colors.muted,
    fontFamily: fonts.bodySemi,
    fontSize: 15,
  },
  headline: {
    fontFamily: fonts.display,
    fontSize: 28,
    letterSpacing: -0.6,
    color: colors.text,
    marginTop: spacing.md,
    width: "100%",
  },
  sub: {
    color: colors.muted,
    fontFamily: fonts.body,
    fontSize: 15,
    lineHeight: 22,
    marginBottom: 8,
    maxWidth: 300,
  },
  error: {
    color: colors.danger,
    fontFamily: fonts.body,
    textAlign: "center",
  },
  link: {
    color: colors.accent,
    textAlign: "center",
    marginTop: 16,
    fontFamily: fonts.bodySemi,
  },
});
