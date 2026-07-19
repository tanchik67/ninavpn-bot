import { useCallback, useState } from "react";
import { useFocusEffect } from "expo-router";
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
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
    <View style={styles.wrap}>
      <Text style={styles.title}>Поддержка</Text>
      <TextInput
        style={styles.input}
        placeholder="Тема"
        placeholderTextColor={colors.muted}
        value={subject}
        onChangeText={setSubject}
      />
      <TextInput
        style={[styles.input, styles.area]}
        placeholder="Опишите проблему"
        placeholderTextColor={colors.muted}
        multiline
        value={body}
        onChangeText={setBody}
      />
      {!!error && <Text style={styles.error}>{error}</Text>}
      <Pressable style={styles.btn} onPress={submit} disabled={busy}>
        {busy ? (
          <ActivityIndicator color={colors.bg} />
        ) : (
          <Text style={styles.btnText}>Отправить</Text>
        )}
      </Pressable>
      <FlatList
        data={tickets}
        keyExtractor={(t) => t.id}
        style={{ marginTop: 16 }}
        renderItem={({ item }) => (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>{item.subject}</Text>
            <Text style={styles.muted}>{item.status}</Text>
            <Text style={styles.body}>{item.body}</Text>
          </View>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, padding: 20 },
  title: { color: colors.text, fontSize: 28, fontWeight: "800", marginBottom: 12 },
  input: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: 12,
    padding: 14,
    color: colors.text,
    marginBottom: 10,
  },
  area: { minHeight: 100, textAlignVertical: "top" },
  btn: {
    backgroundColor: colors.accent,
    borderRadius: 12,
    padding: 14,
    alignItems: "center",
  },
  btnText: { color: colors.bg, fontWeight: "700" },
  card: {
    backgroundColor: colors.surface,
    borderRadius: 12,
    padding: 14,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: colors.border,
  },
  cardTitle: { color: colors.text, fontWeight: "700" },
  muted: { color: colors.muted, marginTop: 4 },
  body: { color: colors.text, marginTop: 8 },
  error: { color: colors.danger, marginBottom: 8 },
});
