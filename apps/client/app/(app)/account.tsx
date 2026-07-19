import { router } from "expo-router";
import { useState } from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { BrandMark } from "../../src/components/BrandMark";
import { Field } from "../../src/components/Field";
import { GlassCard } from "../../src/components/GlassCard";
import { GradientButton } from "../../src/components/GradientButton";
import { ScreenBackground } from "../../src/components/ScreenBackground";
import { api, API_URL } from "../../src/lib/api";
import { useAuth } from "../../src/lib/auth";
import { colors } from "../../src/lib/theme";

type User = { id: string; email: string; tg_id?: number | null };

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
      setMsg("Telegram привязан");
    } catch (e: any) {
      setError(e?.message || "Не удалось привязать");
    } finally {
      setBusy(false);
    }
  };

  const unlink = async () => {
    setBusy(true);
    setError("");
    try {
      await api<User>("/api/v1/auth/unlink-telegram", { method: "POST" });
      await refreshMe();
      setMsg("Telegram отвязан");
    } catch (e: any) {
      setError(e?.message || "Ошибка");
    } finally {
      setBusy(false);
    }
  };

  return (
    <ScreenBackground>
      <ScrollView contentContainerStyle={styles.scroll}>
        <BrandMark size={26} />
        <Text style={styles.title}>Settings</Text>

        <GlassCard style={{ gap: 6 }}>
          <Text style={styles.section}>General</Text>
          <Text style={styles.row}>Email: {user?.email}</Text>
          <Text style={styles.row}>
            Telegram: {user?.tg_id ? `id ${user.tg_id}` : "не привязан"}
          </Text>
        </GlassCard>

        <GlassCard style={{ gap: 10 }}>
          <Text style={styles.section}>Telegram</Text>
          <Text style={styles.hint}>
            В боте: /linkcabinet → вставьте код сюда. Уведомления о доступе придут в Telegram.
          </Text>
          {!user?.tg_id ? (
            <>
              <Field placeholder="Код из бота" value={code} onChangeText={setCode} autoCapitalize="none" />
              <GradientButton
                label="Привязать"
                onPress={link}
                busy={busy}
                disabled={code.trim().length < 4}
              />
            </>
          ) : (
            <GradientButton variant="ghost" label="Отвязать Telegram" onPress={unlink} busy={busy} />
          )}
          {!!msg && <Text style={styles.ok}>{msg}</Text>}
          {!!error && <Text style={styles.error}>{error}</Text>}
        </GlassCard>

        <GlassCard style={{ gap: 10 }}>
          <Text style={styles.section}>Support</Text>
          <GradientButton variant="ghost" label="Написать в поддержку" onPress={() => router.push("/(app)/support")} />
        </GlassCard>

        <Text style={styles.api}>API: {API_URL}</Text>
        <GradientButton variant="ghost" label="Выйти" onPress={logout} />
      </ScrollView>
    </ScreenBackground>
  );
}

const styles = StyleSheet.create({
  scroll: { padding: 20, paddingTop: 56, paddingBottom: 40, gap: 14 },
  title: { color: colors.text, fontSize: 28, fontWeight: "900" },
  section: { color: colors.text, fontWeight: "800", fontSize: 16 },
  row: { color: colors.muted },
  hint: { color: colors.muted, lineHeight: 20 },
  ok: { color: colors.success },
  error: { color: colors.danger },
  api: { color: colors.muted, fontSize: 11 },
});
