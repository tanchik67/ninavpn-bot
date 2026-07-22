import { goBackOr } from "../../src/lib/nav";
import { useState } from "react";
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
} from "react-native";
import { AppText as Text } from "../../src/components/AppText";
import { Field } from "../../src/components/Field";
import { GlassCard } from "../../src/components/GlassCard";
import { ScreenTitle } from "../../src/components/NinaLogo";
import { PrimaryButton } from "../../src/components/PrimaryButton";
import { ScreenBackground } from "../../src/components/ScreenBackground";
import { api } from "../../src/lib/api";
import { useAuth } from "../../src/lib/auth";
import { useI18n } from "../../src/lib/i18n";
import { colors, fonts, spacing } from "../../src/lib/theme";

export default function ChangePasswordScreen() {
  const { user, refreshMe } = useAuth();
  const { t } = useI18n();
  const hasPassword = !!user?.has_password;
  const [current, setCurrent] = useState("");
  const [password, setPassword] = useState("");
  const [password2, setPassword2] = useState("");
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [busy, setBusy] = useState(false);

  const errText = (e: unknown) => {
    const raw = e instanceof Error ? e.message : String(e);
    if (raw.includes("invalid_current_password")) {
      return t("changePassword.errorCurrent");
    }
    try {
      const j = JSON.parse(raw);
      if (j?.detail) return String(j.detail);
    } catch {
      /* ignore */
    }
    return raw || t("changePassword.errorGeneric");
  };

  const onSubmit = async () => {
    if (password.length < 8) {
      setError(t("password.errorTooShort"));
      return;
    }
    if (password !== password2) {
      setError(t("password.errorMismatch"));
      return;
    }
    if (hasPassword && !current) {
      setError(t("changePassword.errorNeedCurrent"));
      return;
    }
    setBusy(true);
    setError("");
    setOk("");
    try {
      await api("/api/v1/auth/password/change", {
        method: "POST",
        body: JSON.stringify({
          current_password: hasPassword ? current : null,
          new_password: password,
        }),
      });
      await refreshMe();
      setCurrent("");
      setPassword("");
      setPassword2("");
      setOk(t("changePassword.success"));
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
          <Pressable onPress={() => goBackOr("/(app)/(tabs)/profile")} hitSlop={12}>
            <Text style={styles.back}>{t("common.back")}</Text>
          </Pressable>
          <ScreenTitle>{t("changePassword.title")}</ScreenTitle>
          <Text style={styles.sub}>
            {hasPassword ? t("changePassword.subtitleHas") : t("changePassword.subtitleSet")}
          </Text>

          <GlassCard style={{ gap: 12 }}>
            {hasPassword && (
              <Field
                label={t("changePassword.current")}
                secureTextEntry
                placeholder="••••••••"
                value={current}
                onChangeText={setCurrent}
              />
            )}
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
            {!!ok && <Text style={styles.ok}>{ok}</Text>}
            {!!error && <Text style={styles.error}>{error}</Text>}
            <PrimaryButton label={t("common.save")} onPress={onSubmit} busy={busy} />
          </GlassCard>
        </ScrollView>
      </KeyboardAvoidingView>
    </ScreenBackground>
  );
}

const styles = StyleSheet.create({
  scroll: {
    paddingHorizontal: spacing.screen,
    paddingTop: 56,
    paddingBottom: 100,
    gap: 8,
  },
  back: { color: colors.accent, fontFamily: fonts.bodySemi, marginBottom: 8 },
  sub: {
    fontFamily: fonts.body,
    color: colors.muted,
    marginBottom: spacing.sm,
    lineHeight: 22,
  },
  ok: { color: colors.success, fontFamily: fonts.body },
  error: { color: colors.danger, fontFamily: fonts.body },
});
