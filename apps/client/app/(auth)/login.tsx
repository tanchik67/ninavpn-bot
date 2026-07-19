import { Link, router } from "expo-router";
import { useState } from "react";
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, Text, View } from "react-native";
import { BrandMark } from "../../src/components/BrandMark";
import { Field } from "../../src/components/Field";
import { GlassCard } from "../../src/components/GlassCard";
import { GradientButton } from "../../src/components/GradientButton";
import { ScreenBackground } from "../../src/components/ScreenBackground";
import { useAuth } from "../../src/lib/auth";
import { colors } from "../../src/lib/theme";

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
        <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
          <BrandMark size={40} />
          <Text style={styles.headline}>Welcome to{"\n"}Unlimited Freedom.</Text>
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
            <GradientButton label="Get Started" onPress={onSubmit} busy={busy} />
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
  scroll: { flexGrow: 1, padding: 24, paddingTop: 72, gap: 14, justifyContent: "center" },
  headline: {
    color: colors.text,
    fontSize: 28,
    fontWeight: "800",
    lineHeight: 34,
    marginTop: 8,
  },
  sub: { color: colors.muted, marginBottom: 8 },
  link: { color: colors.accentPink, textAlign: "center", marginTop: 8, fontWeight: "700" },
  error: { color: colors.danger },
});
