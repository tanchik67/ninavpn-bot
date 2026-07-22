import { router } from "expo-router";
import { goBackOr } from "../../src/lib/nav";
import { useCallback, useState } from "react";
import { useFocusEffect } from "expo-router";
import { FlatList, Pressable, StyleSheet, View } from "react-native";
import { AppText as Text } from "../../src/components/AppText";
import { Field } from "../../src/components/Field";
import { GlassCard } from "../../src/components/GlassCard";
import { NinaLogo, ScreenTitle } from "../../src/components/NinaLogo";
import { PrimaryButton } from "../../src/components/PrimaryButton";
import { ScreenBackground } from "../../src/components/ScreenBackground";
import { api } from "../../src/lib/api";
import { useI18n } from "../../src/lib/i18n";
import { colors, fonts, spacing } from "../../src/lib/theme";

type Ticket = {
  id: string;
  subject: string;
  body: string;
  status: string;
  created_at: string;
};

export default function SupportScreen() {
  const { t } = useI18n();
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    const data = await api<Ticket[]>("/api/v1/support/tickets");
    setTickets(data);
  }, []);

  useFocusEffect(
    useCallback(() => {
      load().catch(() => setError(t("support.errorLoad")));
    }, [load, t])
  );

  const submit = async () => {
    setBusy(true);
    setError("");
    try {
      await api("/api/v1/support/tickets", {
        method: "POST",
        body: JSON.stringify({ subject, body }),
      });
      setSubject("");
      setBody("");
      await load();
    } catch (e: any) {
      setError(e?.message || t("support.errorSend"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <ScreenBackground>
      <View style={styles.wrap}>
        <Pressable onPress={() => goBackOr("/(app)/(tabs)/settings")} hitSlop={12}>
          <Text style={styles.back}>{t("common.back")}</Text>
        </Pressable>
        <NinaLogo size={24} />
        <ScreenTitle>{t("support.title")}</ScreenTitle>
        <PrimaryButton
          label={t("support.openChat")}
          onPress={() => router.push("/(app)/support-chat")}
          style={{ marginBottom: 12 }}
        />
        <GlassCard style={{ gap: 10 }}>
          <Field
            placeholder={t("support.subjectPlaceholder")}
            value={subject}
            onChangeText={setSubject}
          />
          <Field
            placeholder={t("support.bodyPlaceholder")}
            value={body}
            onChangeText={setBody}
            multiline
            style={{ minHeight: 100, textAlignVertical: "top" }}
          />
          {!!error && <Text style={styles.error}>{error}</Text>}
          <PrimaryButton label={t("support.submitTicket")} onPress={submit} busy={busy} />
        </GlassCard>
        <FlatList
          data={tickets}
          keyExtractor={(tkt) => tkt.id}
          style={{ marginTop: 12 }}
          contentContainerStyle={{ gap: 10, paddingBottom: 100 }}
          renderItem={({ item }) => (
            <GlassCard>
              <Text style={styles.cardTitle}>{item.subject}</Text>
              <Text style={styles.muted}>{item.status}</Text>
              <Text style={styles.body}>{item.body}</Text>
            </GlassCard>
          )}
        />
      </View>
    </ScreenBackground>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, padding: spacing.screen, paddingTop: 56 },
  back: { color: colors.accent, fontFamily: fonts.bodySemi, marginBottom: 8 },
  cardTitle: { color: colors.text, fontFamily: fonts.bodyBold },
  muted: { color: colors.muted, marginTop: 4, fontFamily: fonts.body },
  body: { color: colors.text, marginTop: 8, fontFamily: fonts.body },
  error: { color: colors.danger, fontFamily: fonts.body },
});
