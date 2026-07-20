import { router } from "expo-router";
import { useCallback, useEffect, useRef, useState } from "react";
import { useFocusEffect } from "expo-router";
import {
  FlatList,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { ScreenBackground } from "../../src/components/ScreenBackground";
import { api } from "../../src/lib/api";
import { colors, fonts, radii, spacing } from "../../src/lib/theme";

type Message = {
  id: string;
  body: string;
  created_at: string;
  is_staff: boolean;
};

type Chat = {
  ticket: { id: string; status: string };
  messages: Message[];
};

export default function SupportChatScreen() {
  const [chat, setChat] = useState<Chat | null>(null);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const listRef = useRef<FlatList>(null);

  const load = useCallback(async () => {
    const data = await api<Chat>("/api/v1/support/chat");
    setChat(data);
  }, []);

  useFocusEffect(
    useCallback(() => {
      load().catch(() => setError("Не удалось загрузить чат"));
      const timer = setInterval(() => {
        load().catch(() => {});
      }, 8000);
      return () => clearInterval(timer);
    }, [load])
  );

  useEffect(() => {
    if (chat?.messages.length) {
      setTimeout(() => listRef.current?.scrollToEnd({ animated: true }), 100);
    }
  }, [chat?.messages.length]);

  const send = async () => {
    const body = text.trim();
    if (!body || !chat || sending) return;
    setSending(true);
    setError("");
    try {
      const msg = await api<Message>(
        `/api/v1/support/tickets/${chat.ticket.id}/messages`,
        {
          method: "POST",
          body: JSON.stringify({ body }),
        }
      );
      setText("");
      setChat((prev) =>
        prev ? { ...prev, messages: [...prev.messages, msg] } : prev
      );
    } catch (e: any) {
      setError(e?.message || "Не удалось отправить");
    } finally {
      setSending(false);
    }
  };

  return (
    <ScreenBackground>
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        keyboardVerticalOffset={Platform.OS === "ios" ? 8 : 0}
      >
        <View style={styles.header}>
          <Pressable onPress={() => router.back()} hitSlop={12}>
            <Text style={styles.back}>‹ Назад</Text>
          </Pressable>
          <Text style={styles.title}>Поддержка</Text>
          <View style={{ width: 64 }} />
        </View>

        {chat?.messages.length === 0 ? (
          <View style={styles.empty}>
            <Text style={styles.emptyEmoji}>💬</Text>
            <Text style={styles.emptyText}>
              Напишите сообщение — ответим в этом чате
            </Text>
          </View>
        ) : (
          <FlatList
            ref={listRef}
            data={chat?.messages ?? []}
            keyExtractor={(m) => m.id}
            contentContainerStyle={styles.messages}
            renderItem={({ item }) => (
              <View
                style={[
                  styles.bubble,
                  item.is_staff ? styles.bubbleStaff : styles.bubbleUser,
                ]}
              >
                <Text style={styles.bubbleText}>{item.body}</Text>
                <Text style={styles.time}>
                  {new Date(item.created_at).toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </Text>
              </View>
            )}
          />
        )}

        {!!error && <Text style={styles.error}>{error}</Text>}

        <View style={styles.inputRow}>
          <TextInput
            style={styles.input}
            placeholder="Сообщение..."
            placeholderTextColor={colors.muted}
            value={text}
            onChangeText={setText}
            multiline
            maxLength={5000}
          />
          <Pressable
            onPress={send}
            disabled={sending || !text.trim()}
            style={[styles.sendBtn, (!text.trim() || sending) && { opacity: 0.4 }]}
          >
            <Text style={styles.sendText}>↑</Text>
          </Pressable>
        </View>
      </KeyboardAvoidingView>
    </ScreenBackground>
  );
}

const styles = StyleSheet.create({
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacing.md,
    paddingTop: 56,
    paddingBottom: 12,
  },
  back: {
    color: colors.accent,
    fontSize: 16,
    fontFamily: fonts.bodySemi,
    width: 64,
  },
  title: {
    color: colors.text,
    fontSize: 17,
    fontFamily: fonts.displayBold,
  },
  empty: { flex: 1, justifyContent: "center", paddingHorizontal: 32, alignItems: "center" },
  emptyEmoji: { fontSize: 32, marginBottom: 12 },
  emptyText: {
    color: colors.muted,
    textAlign: "center",
    lineHeight: 22,
    fontFamily: fonts.body,
  },
  messages: { padding: spacing.md, paddingBottom: 8, gap: 10 },
  bubble: {
    maxWidth: "82%",
    padding: 12,
    borderRadius: radii.md,
    marginBottom: 4,
  },
  bubbleUser: {
    alignSelf: "flex-end",
    backgroundColor: colors.accent,
    borderBottomRightRadius: 4,
  },
  bubbleStaff: {
    alignSelf: "flex-start",
    backgroundColor: colors.glassFill,
    borderBottomLeftRadius: 4,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.glassBorder,
  },
  bubbleText: {
    color: colors.text,
    lineHeight: 20,
    fontFamily: fonts.body,
  },
  time: {
    color: "rgba(255,255,255,0.55)",
    fontSize: 10,
    marginTop: 6,
    alignSelf: "flex-end",
    fontFamily: fonts.body,
  },
  error: {
    color: colors.danger,
    textAlign: "center",
    paddingHorizontal: 16,
    marginBottom: 4,
    fontFamily: fonts.body,
  },
  inputRow: {
    flexDirection: "row",
    alignItems: "flex-end",
    padding: 12,
    gap: 8,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.hairline,
    backgroundColor: "rgba(6,6,8,0.92)",
  },
  input: {
    flex: 1,
    backgroundColor: colors.glassFill,
    borderRadius: radii.pill,
    paddingHorizontal: 16,
    paddingVertical: 10,
    color: colors.text,
    maxHeight: 100,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.glassBorder,
    fontFamily: fonts.body,
  },
  sendBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.accent,
    alignItems: "center",
    justifyContent: "center",
  },
  sendText: { color: "#fff", fontSize: 18, fontWeight: "700" },
});
