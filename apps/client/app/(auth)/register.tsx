import { Link, router } from "expo-router";
import { useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { useAuth } from "../../src/lib/auth";
import { colors } from "../../src/lib/theme";

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
      router.replace("/(app)/plans");
    } catch (e: any) {
      setError(e?.message || "Ошибка регистрации");
    } finally {
      setBusy(false);
    }
  };

  return (
    <View style={styles.wrap}>
      <Text style={styles.brand}>NinaVPN</Text>
      <Text style={styles.sub}>Регистрация</Text>
      <TextInput
        style={styles.input}
        autoCapitalize="none"
        keyboardType="email-address"
        placeholder="Email"
        placeholderTextColor={colors.muted}
        value={email}
        onChangeText={setEmail}
      />
      <TextInput
        style={styles.input}
        secureTextEntry
        placeholder="Пароль (мин. 8)"
        placeholderTextColor={colors.muted}
        value={password}
        onChangeText={setPassword}
      />
      {!!error && <Text style={styles.error}>{error}</Text>}
      <Pressable style={styles.btn} onPress={onSubmit} disabled={busy}>
        {busy ? (
          <ActivityIndicator color={colors.bg} />
        ) : (
          <Text style={styles.btnText}>Зарегистрироваться</Text>
        )}
      </Pressable>
      <Link href="/(auth)/login" style={styles.link}>
        Уже есть аккаунт
      </Link>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, padding: 24, justifyContent: "center", gap: 12 },
  brand: { color: colors.text, fontSize: 36, fontWeight: "800" },
  sub: { color: colors.muted, marginBottom: 12 },
  input: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: 12,
    padding: 14,
    color: colors.text,
  },
  btn: {
    backgroundColor: colors.accent,
    borderRadius: 12,
    padding: 16,
    alignItems: "center",
    marginTop: 8,
  },
  btnText: { color: colors.bg, fontWeight: "700", fontSize: 16 },
  link: { color: colors.accent, marginTop: 16, textAlign: "center" },
  error: { color: colors.danger },
});
