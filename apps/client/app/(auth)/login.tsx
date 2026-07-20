import { Link, router } from "expo-router";
import { useState } from "react";
import {
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { Field } from "../../src/components/Field";
import { NinaLogo } from "../../src/components/NinaLogo";
import { PrimaryButton } from "../../src/components/PrimaryButton";
import { ScreenBackground } from "../../src/components/ScreenBackground";
import { GlassCard } from "../../src/components/GlassCard";
import { useAuth } from "../../src/lib/auth";
import { colors, fonts, spacing } from "../../src/lib/theme";

export default function LoginScreen() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const onSubmit = async () => {
    setBusy(true);
    setError("");
    try {
      await login(email.trim(), password);
      router.replace("/(app)/home");
    } catch (e: any) {
      setError(e?.message || "Ошибка входа");
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
          <Text style={styles.headline}>Вход</Text>
          <Text style={styles.sub}>Войдите в кабинет NinaVPN</Text>

          <GlassCard style={{ gap: 12 }}>
            <Field
              label="Email"
              autoCapitalize="none"
              keyboardType="email-address"
              placeholder="you@email.com"
              value={email}
              onChangeText={setEmail}
            />
            <Field
              label="Пароль"
              secureTextEntry
              placeholder="••••••••"
              value={password}
              onChangeText={setPassword}
            />
            {!!error && <Text style={styles.error}>{error}</Text>}
            <PrimaryButton label="Продолжить" onPress={onSubmit} busy={busy} />
          </GlassCard>

          <Link href="/(auth)/register" style={styles.link}>
            Создать аккаунт
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
  error: { color: colors.danger, fontFamily: fonts.body },
});
