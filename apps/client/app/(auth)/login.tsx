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
import { NinaLogo } from "../../src/components/NinaLogo";
import { PrimaryButton } from "../../src/components/PrimaryButton";
import { ScreenBackground } from "../../src/components/ScreenBackground";
import { GlassCard } from "../../src/components/GlassCard";
import { SocialAuthButtons } from "../../src/components/SocialAuthButtons";
import { useAuth } from "../../src/lib/auth";
import { useI18n } from "../../src/lib/i18n";
import { colors, fonts, spacing } from "../../src/lib/theme";

export default function LoginScreen() {
  const { login } = useAuth();
  const { t } = useI18n();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const onSubmit = async () => {
    setBusy(true);
    setError("");
    try {
      await login(email.trim(), password);
      router.replace("/(app)/(tabs)/home");
    } catch (e: any) {
      setError(e?.message || t("login.errorGeneric"));
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
          <Text style={styles.headline}>{t("login.title")}</Text>
          <Text style={styles.sub}>{t("login.subtitle")}</Text>

          <GlassCard style={{ gap: 12 }}>
            <Field
              label={t("common.email")}
              autoCapitalize="none"
              keyboardType="email-address"
              placeholder={t("common.emailPlaceholder")}
              value={email}
              onChangeText={setEmail}
            />
            <Field
              label={t("common.password")}
              secureTextEntry
              placeholder="••••••••"
              value={password}
              onChangeText={setPassword}
            />
            <Link href="/(auth)/forgot-password" style={styles.forgot}>
              {t("login.forgotPassword")}
            </Link>
            {!!error && <Text style={styles.error}>{error}</Text>}
            <PrimaryButton label={t("common.continue")} onPress={onSubmit} busy={busy} />
            <SocialAuthButtons
              onSuccess={() => router.replace("/(app)/(tabs)/home")}
              onError={setError}
            />
          </GlassCard>

          <Link href="/(auth)/register" style={styles.link}>
            {t("login.createAccount")}
          </Link>
        </ScrollView>
      </KeyboardAvoidingView>
    </ScreenBackground>
  );
}

const styles = StyleSheet.create({
  scroll: {
    flexGrow: 1,
    padding: spacing.xl,
    paddingTop: 72,
    gap: spacing.sm,
    justifyContent: "center",
  },
  headline: {
    fontFamily: fonts.display,
    fontSize: 34,
    letterSpacing: -0.8,
    color: colors.text,
    marginTop: spacing.md,
  },
  sub: {
    fontFamily: fonts.body,
    color: colors.muted,
    marginBottom: spacing.sm,
  },
  link: {
    color: colors.accent,
    textAlign: "center",
    marginTop: spacing.sm,
    fontFamily: fonts.bodySemi,
  },
  forgot: {
    color: colors.accent,
    alignSelf: "flex-end",
    marginTop: -4,
    fontFamily: fonts.bodySemi,
    fontSize: 13,
  },
  error: { color: colors.danger, fontFamily: fonts.body },
});
