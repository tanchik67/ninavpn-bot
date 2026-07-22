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
import { api } from "../../src/lib/api";
import { useI18n } from "../../src/lib/i18n";
import { colors, fonts, spacing } from "../../src/lib/theme";

type Step = "email" | "reset";

type ForgotResp = { detail: string; dev_code?: string | null };

export default function ForgotPasswordScreen() {
  const { t } = useI18n();
  const [step, setStep] = useState<Step>("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [password2, setPassword2] = useState("");
  const [hint, setHint] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const errText = (e: unknown) => {
    const raw = e instanceof Error ? e.message : String(e);
    if (raw.includes("invalid_code")) return t("forgot.errorInvalidCode");
    if (raw.includes("banned")) return t("forgot.errorBanned");
    try {
      const j = JSON.parse(raw);
      if (j?.detail) return String(j.detail);
    } catch {
      /* ignore */
    }
    return raw || t("common.error");
  };

  const sendCode = async () => {
    const em = email.trim().toLowerCase();
    if (!em.includes("@")) {
      setError(t("forgot.errorEnterEmail"));
      return;
    }
    setBusy(true);
    setError("");
    setHint("");
    try {
      const res = await api<ForgotResp>("/api/v1/auth/password/forgot", {
        method: "POST",
        auth: false,
        body: JSON.stringify({ email: em }),
      });
      setStep("reset");
      if (res.dev_code) {
        setHint(t("forgot.hintDevCode", { code: res.dev_code }));
        setCode(res.dev_code);
      } else {
        setHint(t("forgot.hintSent"));
      }
    } catch (e) {
      setError(errText(e));
    } finally {
      setBusy(false);
    }
  };

  const reset = async () => {
    if (password.length < 8) {
      setError(t("password.errorTooShort"));
      return;
    }
    if (password !== password2) {
      setError(t("password.errorMismatch"));
      return;
    }
    setBusy(true);
    setError("");
    try {
      await api("/api/v1/auth/password/reset", {
        method: "POST",
        auth: false,
        body: JSON.stringify({
          email: email.trim().toLowerCase(),
          code: code.trim(),
          new_password: password,
        }),
      });
      router.replace("/(auth)/login");
    } catch (e) {
      setError(errText(e));
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
          <Text style={styles.headline}>{t("forgot.title")}</Text>
          <Text style={styles.sub}>
            {step === "email" ? t("forgot.subtitleEmail") : t("forgot.subtitleReset")}
          </Text>

          <GlassCard style={{ gap: 12 }}>
            {step === "email" ? (
              <>
                <Field
                  label={t("common.email")}
                  autoCapitalize="none"
                  keyboardType="email-address"
                  placeholder={t("common.emailPlaceholder")}
                  value={email}
                  onChangeText={setEmail}
                />
                {!!error && <Text style={styles.error}>{error}</Text>}
                <PrimaryButton
                  label={t("forgot.getCode")}
                  onPress={sendCode}
                  busy={busy}
                />
              </>
            ) : (
              <>
                <Field
                  label={t("common.email")}
                  autoCapitalize="none"
                  value={email}
                  editable={false}
                />
                <Field
                  label={t("forgot.codeLabel")}
                  autoCapitalize="none"
                  keyboardType="number-pad"
                  placeholder={t("forgot.codePlaceholder")}
                  value={code}
                  onChangeText={setCode}
                />
                <Field
                  label={t("password.new")}
                  secureTextEntry
                  placeholder="••••••••"
                  value={password}
                  onChangeText={setPassword}
                />
                <Field
                  label={t("password.confirm")}
                  secureTextEntry
                  placeholder="••••••••"
                  value={password2}
                  onChangeText={setPassword2}
                />
                {!!hint && <Text style={styles.hint}>{hint}</Text>}
                {!!error && <Text style={styles.error}>{error}</Text>}
                <PrimaryButton
                  label={t("forgot.savePassword")}
                  onPress={reset}
                  busy={busy}
                />
                <PrimaryButton
                  label={t("forgot.resendCode")}
                  variant="secondary"
                  onPress={sendCode}
                  busy={busy}
                />
              </>
            )}
          </GlassCard>

          <Link href="/(auth)/login" style={styles.link}>
            {t("forgot.backToLogin")}
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
    lineHeight: 22,
  },
  link: {
    color: colors.accent,
    textAlign: "center",
    marginTop: spacing.sm,
    fontFamily: fonts.bodySemi,
  },
  error: { color: colors.danger, fontFamily: fonts.body },
  hint: { color: colors.muted, fontFamily: fonts.body, lineHeight: 20 },
});
