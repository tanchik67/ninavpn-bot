import { router } from "expo-router";
import { useState } from "react";
import { Pressable, StyleSheet, View } from "react-native";
import { AppText as Text } from "../../src/components/AppText";
import { NinaLogo } from "../../src/components/NinaLogo";
import { PrimaryButton } from "../../src/components/PrimaryButton";
import { ScreenBackground } from "../../src/components/ScreenBackground";
import { SocialAuthButtons } from "../../src/components/SocialAuthButtons";
import { useI18n } from "../../src/lib/i18n";
import { colors, fonts, spacing } from "../../src/lib/theme";

export default function WelcomeScreen() {
  const { t, locale, setLocale } = useI18n();
  const [error, setError] = useState("");

  return (
    <ScreenBackground>
      <View style={styles.wrap}>
        <View style={styles.top}>
          <NinaLogo size={36} />
          <Text style={styles.title}>{t("welcome.title")}</Text>
          <Text style={styles.sub}>{t("welcome.subtitle")}</Text>
        </View>
        <View style={styles.bottom}>
          {!!error && <Text style={styles.error}>{error}</Text>}
          <SocialAuthButtons
            onSuccess={() => router.replace("/(app)/(tabs)/home")}
            onError={setError}
          />
          <PrimaryButton
            label={t("welcome.loginEmail")}
            variant="secondary"
            onPress={() => router.push("/(auth)/login")}
            style={{ marginTop: 8 }}
          />
          {locale === "ru" ? (
            <Pressable
              onPress={() => setLocale("en")}
              style={styles.langBtn}
              hitSlop={8}
            >
              <Text style={styles.langText}>{t("welcome.continueEn")}</Text>
            </Pressable>
          ) : (
            <Pressable
              onPress={() => setLocale("ru")}
              style={styles.langBtn}
              hitSlop={8}
            >
              <Text style={styles.langText}>{t("welcome.continueRu")}</Text>
            </Pressable>
          )}
        </View>
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
  bottom: { gap: 4 },
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
  error: {
    color: colors.danger,
    fontFamily: fonts.body,
    textAlign: "center",
    marginBottom: 4,
  },
  langBtn: {
    marginTop: 20,
    alignSelf: "center",
    paddingVertical: 8,
  },
  langText: {
    color: colors.muted,
    fontFamily: fonts.body,
    fontSize: 13,
  },
});
