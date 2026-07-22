import { router } from "expo-router";
import { goBackOr } from "../../src/lib/nav";
import { useState } from "react";
import { Pressable, ScrollView, StyleSheet } from "react-native";
import { AppText as Text } from "../../src/components/AppText";
import { Field } from "../../src/components/Field";
import { GlassCard } from "../../src/components/GlassCard";
import { NinaLogo, ScreenTitle } from "../../src/components/NinaLogo";
import { PrimaryButton } from "../../src/components/PrimaryButton";
import { ScreenBackground } from "../../src/components/ScreenBackground";
import { api, API_URL } from "../../src/lib/api";
import { useAuth } from "../../src/lib/auth";
import { useI18n } from "../../src/lib/i18n";
import { colors, fonts, spacing } from "../../src/lib/theme";

type User = { id: string; email: string; tg_id?: number | null };

export default function AccountScreen() {
  const { user, logout, refreshMe } = useAuth();
  const { t } = useI18n();
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
      setMsg(t("account.tgLinked"));
    } catch (e: any) {
      setError(e?.message || t("account.errorLink"));
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
      setMsg(t("account.tgUnlinked"));
    } catch (e: any) {
      setError(e?.message || t("common.error"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <ScreenBackground>
      <ScrollView contentContainerStyle={styles.scroll}>
        <Pressable onPress={() => goBackOr("/(app)/(tabs)/profile")} hitSlop={12}>
          <Text style={styles.back}>{t("common.back")}</Text>
        </Pressable>
        <NinaLogo size={24} />
        <ScreenTitle>{t("account.title")}</ScreenTitle>

        <GlassCard style={{ gap: 6 }}>
          <Text style={styles.section}>{t("account.general")}</Text>
          <Text style={styles.row}>
            {t("account.emailRow", { email: user?.email ?? "" })}
          </Text>
          <Text style={styles.row}>
            {user?.tg_id
              ? t("account.tgLinkedId", { id: user.tg_id })
              : `Telegram: ${t("account.tgNotLinked")}`}
          </Text>
        </GlassCard>

        <GlassCard style={{ gap: 10, marginTop: spacing.md }}>
          <Text style={styles.section}>{t("account.telegram")}</Text>
          <Text style={styles.hint}>{t("account.tgHint")}</Text>
          {!user?.tg_id ? (
            <>
              <Field
                placeholder={t("account.codePlaceholder")}
                value={code}
                onChangeText={setCode}
                autoCapitalize="none"
              />
              <PrimaryButton
                label={t("account.link")}
                onPress={link}
                busy={busy}
                disabled={code.trim().length < 4}
              />
            </>
          ) : (
            <PrimaryButton
              variant="secondary"
              label={t("account.unlinkTg")}
              onPress={unlink}
              busy={busy}
            />
          )}
          {!!msg && <Text style={styles.ok}>{msg}</Text>}
          {!!error && <Text style={styles.error}>{error}</Text>}
        </GlassCard>

        <GlassCard style={{ gap: 10, marginTop: spacing.md }}>
          <Text style={styles.section}>{t("account.security")}</Text>
          <PrimaryButton
            variant="secondary"
            label={t("password.change")}
            onPress={() => router.push("/(app)/change-password")}
          />
        </GlassCard>

        <Text style={styles.api}>{t("account.apiLabel", { url: API_URL })}</Text>
        <PrimaryButton variant="secondary" label={t("common.logout")} onPress={logout} />
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
