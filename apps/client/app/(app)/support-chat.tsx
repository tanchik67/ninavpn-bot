import { Redirect, router, useLocalSearchParams } from "expo-router";
import { goBackOr } from "../../src/lib/nav";
import { useCallback, useEffect, useRef, useState } from "react";
import { useFocusEffect } from "expo-router";
import {
  FlatList,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  View,
} from "react-native";
import { AppText as Text, AppTextInput as TextInput } from "../../src/components/AppText";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { ScreenBackground } from "../../src/components/ScreenBackground";
import { api } from "../../src/lib/api";
import { useAuth } from "../../src/lib/auth";
import { useI18n } from "../../src/lib/i18n";
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

function isStaffRole(role?: string) {
  return role === "admin" || role === "support";
}

export default function SupportChatScreen() {
  const insets = useSafeAreaInsets();
  const { user } = useAuth();
  const { t } = useI18n();
  const params = useLocalSearchParams<{ ticketId?: string; email?: string }>();
  const ticketIdParam = Array.isArray(params.ticketId)
    ? params.ticketId[0]
    : params.ticketId;
  const emailParam = Array.isArray(params.email) ? params.email[0] : params.email;

  const staff = isStaffRole(user?.role);
  const staffMode = staff && !!ticketIdParam;

  const [chat, setChat] = useState<Chat | null>(null);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const listRef = useRef<FlatList>(null);
  // Stack screen (no tab dock) — only keep home-indicator inset
  const inputBottomPad = Math.max(insets.bottom, 8);

  const load = useCallback(async () => {
    if (staffMode && ticketIdParam) {
      const data = await api<Chat>(
        `/api/v1/support/admin/tickets/${ticketIdParam}`
      );
      setChat(data);
      return;
    }
    const data = await api<Chat>("/api/v1/support/chat");
    setChat(data);
  }, [staffMode, ticketIdParam]);

  useFocusEffect(
    useCallback(() => {
      if (staff && !ticketIdParam) return;
      load().catch(() => setError(t("supportChat.errorLoad")));
      const timer = setInterval(() => {
        load().catch(() => {});
      }, 8000);
      return () => clearInterval(timer);
    }, [load, staff, ticketIdParam, t])
  );

  useEffect(() => {
    if (chat?.messages.length) {
      setTimeout(() => listRef.current?.scrollToEnd({ animated: true }), 100);
    }
  }, [chat?.messages.length]);

  if (staff && !ticketIdParam) {
    return <Redirect href="/(app)/admin-inbox" />;
  }

  const send = async () => {
    const body = text.trim();
    if (!body || !chat || sending) return;
    setSending(true);
    setError("");
    try {
      const path = staffMode
        ? `/api/v1/support/admin/tickets/${chat.ticket.id}/messages`
        : `/api/v1/support/tickets/${chat.ticket.id}/messages`;
      const msg = await api<Message>(path, {
        method: "POST",
        body: JSON.stringify({ body }),
      });
      setText("");
      setChat((prev) =>
        prev ? { ...prev, messages: [...prev.messages, msg] } : prev
      );
    } catch (e: any) {
      setError(e?.message || t("supportChat.errorSend"));
    } finally {
      setSending(false);
    }
  };

  const title = staffMode
    ? emailParam || t("supportChat.titleClient")
    : t("supportChat.title");

  return (
    <ScreenBackground>
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        keyboardVerticalOffset={Platform.OS === "ios" ? 8 : 0}
      >
        <View style={styles.header}>
          <Pressable onPress={() => goBackOr("/(app)/(tabs)/settings")} hitSlop={12}>
            <Text style={styles.back}>{t("common.back")}</Text>
          </Pressable>
          <Text style={styles.title} numberOfLines={1}>
            {title}
          </Text>
          <View style={{ width: 64 }} />
        </View>

        {chat?.messages.length === 0 ? (
          <View style={styles.empty}>
            <Text style={styles.emptyEmoji}>💬</Text>
            <Text style={styles.emptyText}>
              {staffMode ? t("supportChat.emptyStaff") : t("supportChat.emptyUser")}
            </Text>
          </View>
        ) : (
          <FlatList
            ref={listRef}
            data={chat?.messages ?? []}
            keyExtractor={(m) => m.id}
            contentContainerStyle={[styles.messages, { paddingBottom: 16 }]}
            renderItem={({ item }) => {
              const mine = staffMode ? item.is_staff : !item.is_staff;
              return (
                <View
                  style={[
                    styles.bubble,
                    mine ? styles.bubbleMine : styles.bubbleTheirs,
                  ]}
                >
                  {staffMode && !mine && (
                    <Text style={styles.author}>{t("supportChat.authorClient")}</Text>
                  )}
                  {staffMode && mine && (
                    <Text style={styles.author}>{t("supportChat.authorYou")}</Text>
                  )}
                  <Text style={styles.bubbleText}>{item.body}</Text>
                  <Text style={styles.time}>
                    {new Date(item.created_at).toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </Text>
                </View>
              );
            }}
          />
        )}

        {!!error && <Text style={styles.error}>{error}</Text>}

        <View style={[styles.inputRow, { paddingBottom: inputBottomPad }]}>
          <TextInput
            style={styles.input}
            placeholder={
              staffMode ? t("supportChat.placeholderStaff") : t("supportChat.placeholderUser")
            }
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
    flex: 1,
    textAlign: "center",
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
  bubbleMine: {
    alignSelf: "flex-end",
    backgroundColor: colors.accent,
    borderBottomRightRadius: 4,
  },
  bubbleTheirs: {
    alignSelf: "flex-start",
    backgroundColor: colors.glassFill,
    borderBottomLeftRadius: 4,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.glassBorder,
  },
  author: {
    color: "rgba(255,255,255,0.55)",
    fontSize: 10,
    marginBottom: 4,
    fontFamily: fonts.bodySemi,
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
