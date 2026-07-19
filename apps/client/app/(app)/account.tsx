import { useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { api, API_URL } from "../../src/lib/api";
import { useAuth } from "../../src/lib/auth";
import { colors } from "../../src/lib/theme";

type User = {
  id: string;
  email: string;
  tg_id?: number | null;
};

export default function AccountScreen() {
  const { user, logout, refreshMe } = useAuth();
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");

  const link = async () => {
    setBusy(true);
    setError("");
    setMsg("");
    try {
      await api<User>("/api/v1/auth/link-telegram", {
        method: "POST",
        body: JSON.stringify({ code: code.trim() }),
      });
      await refreshMe();
      setCode("");
      setMsg("Telegram привязан. Проверьте сообщение в боте.");
    } catch (e: any) {
      setError(e?.message || "Не удалось привязать");
    } finally {
      setBusy(false);
    }
  };

  const unlink = async () => {
    setBusy(true);
    setError("");
    setMsg("");
    try {
      await api<User>("/api/v1/auth/unlink-telegram", { method: "POST" });
      await refreshMe();
      setMsg("Telegram отвязан.");
    } catch (e: any) {
      setError(e?.message || "Ошибка отвязки");
    } finally {
      setBusy(false);
    }
  };

  return (
    <View style={styles.wrap}>
      <Text style={styles.title}>Аккаунт</Text>
      <Text style={styles.row}>Email: {user?.email}</Text>
      <Text style={styles.row}>
        Telegram: {user?.tg_id ? `привязан (id ${user.tg_id})` : "не привязан"}
      </Text>
      <Text style={styles.hint}>
        В Telegram-боте отправьте /linkcabinet, скопируйте код и вставьте ниже.
        После привязки уведомления о доступе и окончании подписки придут в Telegram.
      </Text>

      {!user?.tg_id ? (
        <>
          <TextInput
            style={styles.input}
            autoCapitalize="none"
            autoCorrect={false}
            placeholder="Код из бота"
            placeholderTextColor={colors.muted}
            value={code}
            onChangeText={setCode}
          />
          <Pressable style={styles.btn} onPress={link} disabled={busy || code.trim().length < 4}>
            {busy ? (
              <ActivityIndicator color={colors.bg} />
            ) : (
              <Text style={styles.btnText}>Привязать Telegram</Text>
            )}
          </Pressable>
        </>
      ) : (
        <Pressable style={styles.secondary} onPress={unlink} disabled={busy}>
          <Text style={styles.btnText}>Отвязать Telegram</Text>
        </Pressable>
      )}

      {!!msg && <Text style={styles.ok}>{msg}</Text>}
      {!!error && <Text style={styles.error}>{error}</Text>}

      <Text style={styles.api}>API: {API_URL}</Text>
      <Pressable onPress={logout} style={{ marginTop: 24 }}>
        <Text style={styles.logout}>Выйти</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, padding: 20, gap: 10 },
  title: { color: colors.text, fontSize: 28, fontWeight: "800", marginBottom: 8 },
  row: { color: colors.muted, fontSize: 16 },
  hint: { color: colors.muted, marginTop: 12, marginBottom: 8, lineHeight: 20 },
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
    padding: 14,
    alignItems: "center",
  },
  secondary: {
    backgroundColor: colors.surface,
    borderRadius: 12,
    padding: 14,
    alignItems: "center",
    borderWidth: 1,
    borderColor: colors.border,
  },
  btnText: { color: colors.text, fontWeight: "700" },
  ok: { color: colors.accent },
  error: { color: colors.danger },
  api: { color: colors.muted, fontSize: 12, marginTop: 20 },
  logout: { color: colors.muted, textAlign: "center" },
});
