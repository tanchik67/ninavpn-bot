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

const FEATURES = [
  { title: "v2ray + XTLS", body: "Современный протокол и стабильный доступ" },
  { title: "No-Log Policy", body: "Без хранения вашей активности" },
  { title: "До 5 устройств", body: "Один аккаунт — несколько устройств по тарифу" },
];

export default function RegisterScreen() {
  const { register } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const onSubmit = async () => {
    setBusy(true);
    setError("");
    try {
      await register(email.trim(), password);
      router.replace("/(app)/home");
    } catch (e: any) {
      setError(e?.message || "Ошибка регистрации");
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
          <BrandMark size={32} />
          <Text style={styles.headline}>Создайте аккаунт</Text>

          {FEATURES.map((f) => (
            <GlassCard key={f.title} style={styles.feat}>
              <Text style={styles.featTitle}>{f.title}</Text>
              <Text style={styles.featBody}>{f.body}</Text>
            </GlassCard>
          ))}

          <GlassCard style={{ gap: 12, marginTop: 8 }}>
            <Field
              label="Email"
              autoCapitalize="none"
              keyboardType="email-address"
              value={email}
              onChangeText={setEmail}
              placeholder="you@email.com"
            />
            <Field
              label="Пароль (мин. 8)"
              secureTextEntry
              value={password}
              onChangeText={setPassword}
              placeholder="••••••••"
            />
            {!!error && <Text style={styles.error}>{error}</Text>}
            <GradientButton label="Continue" onPress={onSubmit} busy={busy} />
          </GlassCard>

          <Link href="/(auth)/login" style={styles.link}>
            Уже есть аккаунт
          </Link>
        </ScrollView>
      </KeyboardAvoidingView>
    </ScreenBackground>
  );
}

const styles = StyleSheet.create({
  scroll: { padding: 24, paddingTop: 64, paddingBottom: 40, gap: 10 },
  headline: { color: colors.text, fontSize: 26, fontWeight: "800", marginBottom: 6 },
  feat: { paddingVertical: 12 },
  featTitle: { color: colors.text, fontWeight: "800" },
  featBody: { color: colors.muted, marginTop: 4 },
  link: { color: colors.accentPink, textAlign: "center", marginTop: 12, fontWeight: "700" },
  error: { color: colors.danger },
});
