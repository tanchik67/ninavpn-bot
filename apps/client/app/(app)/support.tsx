import { useCallback, useState } from "react";
import { useFocusEffect } from "expo-router";
import { FlatList, StyleSheet, Text, View } from "react-native";
import { BrandMark } from "../../src/components/BrandMark";
import { Field } from "../../src/components/Field";
import { GlassCard } from "../../src/components/GlassCard";
import { GradientButton } from "../../src/components/GradientButton";
import { ScreenBackground } from "../../src/components/ScreenBackground";
import { api } from "../../src/lib/api";
import { colors } from "../../src/lib/theme";

type Ticket = {
  id: string;
  subject: string;
  body: string;
  status: string;
  created_at: string;
};

export default function SupportScreen() {
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
      load().catch(() => setError("Не удалось загрузить обращения"));
    }, [load])
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
      setError(e?.message || "Ошибка отправки");
    } finally {
      setBusy(false);
    }
  };

  return (
    <ScreenBackground>
      <View style={styles.wrap}>
        <BrandMark size={26} />
        <Text style={styles.title}>Support</Text>
        <GlassCard style={{ gap: 10 }}>
          <Field placeholder="Тема" value={subject} onChangeText={setSubject} />
          <Field
            placeholder="Опишите проблему"
            value={body}
            onChangeText={setBody}
            multiline
            style={{ minHeight: 100, textAlignVertical: "top" }}
          />
          {!!error && <Text style={styles.error}>{error}</Text>}
          <GradientButton label="Отправить" onPress={submit} busy={busy} />
        </GlassCard>
        <FlatList
          data={tickets}
          keyExtractor={(t) => t.id}
          style={{ marginTop: 12 }}
          contentContainerStyle={{ gap: 10, paddingBottom: 40 }}
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
  wrap: { flex: 1, padding: 20, paddingTop: 56 },
  title: { color: colors.text, fontSize: 28, fontWeight: "900", marginBottom: 12 },
  cardTitle: { color: colors.text, fontWeight: "800" },
  muted: { color: colors.muted, marginTop: 4 },
  body: { color: colors.text, marginTop: 8 },
  error: { color: colors.danger },
});
