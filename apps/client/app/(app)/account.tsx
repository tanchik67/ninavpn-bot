import { router } from "expo-router";
import { useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text } from "react-native";
import { Field } from "../../src/components/Field";
import { GlassCard } from "../../src/components/GlassCard";
import { NinaLogo, ScreenTitle } from "../../src/components/NinaLogo";
import { PrimaryButton } from "../../src/components/PrimaryButton";
import { ScreenBackground } from "../../src/components/ScreenBackground";
import { api, API_URL } from "../../src/lib/api";
import { useAuth } from "../../src/lib/auth";
import { colors, fonts, spacing } from "../../src/lib/theme";

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
        <Pressable onPress={() => router.back()} hitSlop={12}>
          <Text style={styles.back}>‹ Назад</Text>
        </Pressable>
        <NinaLogo size={24} />
        <ScreenTitle>Аккаунт</ScreenTitle>

        <GlassCard style={{ gap: 6 }}>
          <Text style={styles.section}>Основные</Text>
          <Text style={styles.row}>Email: {user?.email}</Text>
          <Text style={styles.row}>
            Telegram: {user?.tg_id ? `id ${user.tg_id}` : "не привязан"}
          </Text>
        </GlassCard>

        <GlassCard style={{ gap: 10, marginTop: spacing.md }}>
          <Text style={styles.section}>Telegram</Text>
          <Text style={styles.hint}>
            В боте: /linkcabinet → вставьте код сюда.
          </Text>
          {!user?.tg_id ? (
            <>
              <Field
                placeholder="Код из бота"
                value={code}
                onChangeText={setCode}
                autoCapitalize="none"
              />
              <PrimaryButton
                label="Привязать"
                onPress={link}
                busy={busy}
                disabled={code.trim().length < 4}
              />
            </>
          ) : (
            <PrimaryButton
              variant="secondary"
              label="Отвязать Telegram"
              onPress={unlink}
              busy={busy}
            />
          )}
          {!!msg && <Text style={styles.ok}>{msg}</Text>}
          {!!error && <Text style={styles.error}>{error}</Text>}
        </GlassCard>

        <GlassCard style={{ gap: 10, marginTop: spacing.md }}>
          <Text style={styles.section}>Поддержка</Text>
          <PrimaryButton
            variant="secondary"
            label="Чат поддержки"
            onPress={() => router.push("/(app)/support-chat")}
          />
        </GlassCard>

        <Text style={styles.api}>API: {API_URL}</Text>
        <PrimaryButton variant="secondary" label="Выйти" onPress={logout} />
      </ScrollView>
    </ScreenBackground>
  );
}

const styles = StyleSheet.create({
  scroll: {
    padding: spacing.screen,
    paddingTop: 56,
    paddingBottom: 100,
    gap: 8,
  },
  back: { color: colors.accent, fontFamily: fonts.bodySemi, marginBottom: 8 },
  section: {
    color: colors.text,
    fontFamily: fonts.bodyBold,
    fontSize: 15,
  },
  row: { color: colors.muted, fontFamily: fonts.body },
  hint: { color: colors.muted, lineHeight: 20, fontFamily: fonts.body },
  ok: { color: colors.success, fontFamily: fonts.body },
  error: { color: colors.danger, fontFamily: fonts.body },
  api: { color: colors.muted, fontSize: 11, fontFamily: fonts.body, marginTop: 12 },
});
