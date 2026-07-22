import { Link, router } from "expo-router";
import { useState } from "react";
import {
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
} from "react-native";
import { AppText as Text } from "../../src/components/AppText";
import { Field } from "../../src/components/Field";
import { GlassCard } from "../../src/components/GlassCard";
import { NinaLogo } from "../../src/components/NinaLogo";
import { PrimaryButton } from "../../src/components/PrimaryButton";
import { ScreenBackground } from "../../src/components/ScreenBackground";
import { SocialAuthButtons } from "../../src/components/SocialAuthButtons";
import { useAuth } from "../../src/lib/auth";
import { useI18n } from "../../src/lib/i18n";
import { colors, fonts, spacing } from "../../src/lib/theme";

export default function RegisterScreen() {
  const { register } = useAuth();
  const { t } = useI18n();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const onSubmit = async () => {
    setBusy(true);
    setError("");
    try {
      await register(email.trim(), password);
      router.replace("/(app)/(tabs)/home");
    } catch (e: any) {
      setError(e?.message || t("register.errorGeneric"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <ScreenBackground>
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        <ScrollView
          contentContainerStyle={styles.scroll}
          keyboardShouldPersistTaps="handled"
        >
          <NinaLogo size={28} />
          <Text style={styles.headline}>{t("register.title")}</Text>
          <Text style={styles.sub}>{t("register.subtitle")}</Text>

          <GlassCard style={{ gap: 12 }}>
            <Field
              label={t("common.email")}
              autoCapitalize="none"
              keyboardType="email-address"
              value={email}
              onChangeText={setEmail}
              placeholder={t("common.emailPlaceholder")}
            />
            <Field
              label={t("register.passwordLabel")}
              secureTextEntry
              value={password}
              onChangeText={setPassword}
              placeholder="••••••••"
            />
            {!!error && <Text style={styles.error}>{error}</Text>}
            <PrimaryButton label={t("common.continue")} onPress={onSubmit} busy={busy} />
            <SocialAuthButtons
              onSuccess={() => router.replace("/(app)/(tabs)/home")}
              onError={setError}
            />
          </GlassCard>

          <Link href="/(auth)/login" style={styles.link}>
            {t("register.haveAccount")}
          </Link>
        </ScrollView>
      </KeyboardAvoidingView>
    </ScreenBackground>
  );
}

const styles = StyleSheet.create({
  scroll: {
    padding: spacing.xl,
    paddingTop: 72,
    paddingBottom: 40,
    gap: 10,
    justifyContent: "center",
    flexGrow: 1,
  },
  headline: {
    fontFamily: fonts.display,
    fontSize: 32,
    letterSpacing: -0.8,
    color: colors.text,
    marginTop: spacing.md,
  },
  sub: { color: colors.muted, fontFamily: fonts.body, marginBottom: 4 },
  link: {
    color: colors.accent,
    textAlign: "center",
    marginTop: 12,
    fontFamily: fonts.bodySemi,
  },
  error: { color: colors.danger, fontFamily: fonts.body },
});
