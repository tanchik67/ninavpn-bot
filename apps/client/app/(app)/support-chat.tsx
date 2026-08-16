import { Redirect, useLocalSearchParams } from "expo-router";
import { goBackOr } from "../../src/lib/nav";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useFocusEffect } from "expo-router";
import {
  ActivityIndicator,
  FlatList,
  Image,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  View,
} from "react-native";
import { AppText as Text, AppTextInput as TextInput } from "../../src/components/AppText";
import { BackCircleButton } from "../../src/components/BackCircleButton";
import { IosEmoji } from "../../src/components/IosEmoji";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { ScreenBackground } from "../../src/components/ScreenBackground";
import { API_URL, api, getAccessToken } from "../../src/lib/api";
import { formatApiError } from "../../src/lib/apiErrors";
import { useAuth } from "../../src/lib/auth";
import { useI18n } from "../../src/lib/i18n";
import {
  loadCachedAdminTicket,
  peekCachedAdminTicket,
  purgeLegacyAdminSupportCache,
  saveCachedAdminTicket,
} from "../../src/lib/adminSupportCache";
import {
  loadCachedSupportChat,
  saveCachedSupportChat,
} from "../../src/lib/supportChatCache";
import {
  addOutbox,
  bumpOutboxNow,
  loadOutbox,
  markOutboxAttempt,
  removeOutbox,
} from "../../src/lib/supportOutbox";
import {
  flushSupportOutbox,
  pendingOutboxForTicket,
} from "../../src/lib/supportOutboxFlush";
import {
  forceUnlockSupportSend,
  formatMsgTime,
  isSupportSendInFlight,
  parseServerTime,
  sendSupportMessage,
  waitForSupportMessage,
} from "../../src/lib/supportSend";
import {
  pauseAdminSupportPrefetch,
  resumeAdminSupportPrefetch,
} from "../../src/lib/adminSupportPrefetch";
import {
  pauseSupportPrefetch,
  resumeSupportPrefetch,
} from "../../src/lib/supportChatPrefetch";
import { ninaVpnGetStatus } from "../../src/lib/ninaVpn";
import { colors, fonts, radii, spacing } from "../../src/lib/theme";

type Message = {
  id: string;
  body: string;
  created_at: string;
  is_staff: boolean;
  image_url?: string | null;
  client_msg_id?: string | null;
  /** Local-only bubble waiting for server ACK */
  pending?: boolean;
};

type Chat = {
  ticket: { id: string; status: string };
  messages: Message[];
};

/** Deduplicate overlapping chat fetches (focus + poll + remount). */
let chatInFlight: Promise<Chat> | null = null;
let chatLoadAbort: AbortController | null = null;

function abortChatLoads() {
  chatLoadAbort?.abort();
  chatLoadAbort = null;
}

function isStaffRole(role?: string) {
  return role === "admin" || role === "support";
}

function AuthImage({ path }: { path: string }) {
  const [token, setToken] = useState<string | null>(null);
  useEffect(() => {
    void getAccessToken().then(setToken);
  }, []);
  if (!token) {
    return (
      <View style={styles.msgImagePlaceholder}>
        <ActivityIndicator color={colors.accent} />
      </View>
    );
  }
  const uri = path.startsWith("http") ? path : `${API_URL}${path}`;
  return (
    <Image
      source={{ uri, headers: { Authorization: `Bearer ${token}` } }}
      style={styles.msgImage}
      resizeMode="cover"
    />
  );
}

function sameSupportMsg(
  a: { id: string; body?: string; created_at?: string; is_staff?: boolean; client_msg_id?: string | null },
  b: { id: string; body?: string; created_at?: string; is_staff?: boolean; client_msg_id?: string | null }
) {
  if (a.id === b.id) return true;
  const aids = [a.client_msg_id, a.id].filter(Boolean) as string[];
  const bids = [b.client_msg_id, b.id, `${b.id}-0`, `${b.id}-1`].filter(Boolean) as string[];
  if (aids.some((id) => bids.includes(id))) return true;
  if (a.client_msg_id && b.client_msg_id && a.client_msg_id === b.client_msg_id) return true;
  if (
    a.is_staff === b.is_staff &&
    (a.body || "").trim() === (b.body || "").trim() &&
    (a.body || "").trim() &&
    Math.abs(parseServerTime(a.created_at || "") - parseServerTime(b.created_at || "")) <
      180_000
  ) {
    return true;
  }
  return false;
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

  // Instant first paint for admin: memory cache filled by inbox prefetch / row press
  const [chat, setChat] = useState<Chat | null>(() =>
    ticketIdParam ? peekCachedAdminTicket(ticketIdParam) : null
  );
  const [loading, setLoading] = useState(
    () => !(ticketIdParam && peekCachedAdminTicket(ticketIdParam))
  );
  const [text, setText] = useState("");
  const [pendingImage, setPendingImage] = useState<{
    uri: string;
    mime: string;
  } | null>(null);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [vpnHint, setVpnHint] = useState(false);
  const listRef = useRef<FlatList>(null);
  const chatRef = useRef<Chat | null>(null);
  const sendingRef = useRef(false);
  const inputBottomPad = Math.max(insets.bottom, 8) + 14;

  useEffect(() => {
    chatRef.current = chat;
  }, [chat]);

  const mergeChat = useCallback((server: Chat, prev: Chat | null): Chat => {
    if (!prev?.messages?.length) return server;
    const locals = prev.messages.filter((m) => m.id.startsWith("local-"));
    if (!locals.length) return server;
    const now = Date.now();
    const merged = [...server.messages];
    for (const p of locals) {
      const already = server.messages.some((m) => sameSupportMsg(m, p));
      if (already) continue;
      const age = now - parseServerTime(p.created_at);
      const maxAge = p.is_staff ? 30 * 60_000 : 10 * 60_000;
      if (age > maxAge) continue;
      merged.push({
        ...p,
        // Spinner only for a couple of seconds — Telegram often has it already
        pending: !!p.pending && age < 4000,
      });
    }
    merged.sort(
      (a, b) => parseServerTime(a.created_at) - parseServerTime(b.created_at)
    );
    return { ...server, messages: merged };
  }, []);

  const applyLoadedChat = useCallback(
    (data: Chat) => {
      setChat((prev) => {
        const next = mergeChat(data, prev);
        if (!staffMode) void saveCachedSupportChat(next);
        else if (ticketIdParam) {
          void saveCachedAdminTicket({
            ...next,
            user_email: emailParam || undefined,
          });
        }
        return next;
      });
    },
    [staffMode, ticketIdParam, emailParam, mergeChat]
  );

  const load = useCallback(async (opts?: { force?: boolean }) => {
    // Client sends: skip GETs so POSTs aren't starved. Admin inbox/chat must
    // still refresh — otherwise a send-lock re-saves poisoned cache forever.
    if (
      !staffMode &&
      !opts?.force &&
      (sendingRef.current || isSupportSendInFlight())
    ) {
      if (chatRef.current) return chatRef.current;
      throw new Error("network_error");
    }
    const run = async (): Promise<Chat> => {
      const ctrl = new AbortController();
      chatLoadAbort = ctrl;
      try {
        if (staffMode && ticketIdParam) {
          return await api<Chat>(
            `/api/v1/support/admin/tickets/${ticketIdParam}`,
            {
              timeoutMs: 10000,
              retries: 0,
              priority: true,
              signal: ctrl.signal,
            }
          );
        }
        return await api<Chat>("/api/v1/support/chat", {
          timeoutMs: 8000,
          retries: 0,
          signal: ctrl.signal,
        });
      } finally {
        if (chatLoadAbort === ctrl) chatLoadAbort = null;
      }
    };

    if (chatInFlight && !opts?.force) {
      const data = await chatInFlight;
      applyLoadedChat(data);
      return data;
    }
    if (opts?.force) abortChatLoads();
    chatInFlight = run().finally(() => {
      chatInFlight = null;
    });
    const data = await chatInFlight;
    applyLoadedChat(data);
    return data;
  }, [staffMode, ticketIdParam, applyLoadedChat]);

  useFocusEffect(
    useCallback(() => {
      if (staff && !ticketIdParam) return;
      let alive = true;

      (async () => {
        // Paint cached admin chat FIRST (sync memory → AsyncStorage).
        // Never wait on VPN status before showing messages.
        let hadCache = false;
        if (staffMode && ticketIdParam) {
          void purgeLegacyAdminSupportCache();
          const mem = peekCachedAdminTicket(ticketIdParam);
          const cached = mem || (await loadCachedAdminTicket(ticketIdParam));
          if (alive && cached) {
            hadCache = true;
            // Re-attach pending outbox bubbles (cache strips local-* ids)
            const box = await pendingOutboxForTicket(ticketIdParam, true);
            const pendingMsgs: Message[] = box.map((item) => ({
              id: item.id,
              body: item.body,
              created_at: item.createdAt,
              is_staff: true,
              pending: true,
            }));
            const known = new Set(cached.messages.map((m) => m.id));
            const merged = {
              ...cached,
              messages: [
                ...cached.messages,
                ...pendingMsgs.filter((m) => !known.has(m.id)),
              ].sort(
                (a, b) =>
                  parseServerTime(a.created_at) - parseServerTime(b.created_at)
              ),
            };
            setChat(merged);
            setLoading(false);
            setError("");
            // Refresh in background — never block the open on network
            void load({ force: true })
              .then(async () => {
                if (!alive) return;
                setError("");
                // Immediately retry any stuck staff replies for this ticket
                await bumpOutboxNow();
                const n = await flushSupportOutbox({
                  staffOnly: true,
                  ticketId: ticketIdParam,
                  ignoreSchedule: true,
                });
                if (n > 0 && alive) await load({ force: true }).catch(() => {});
              })
              .catch(() => {
                /* keep cached admin chat */
              });
          } else {
            if (alive) setLoading(true);
            let lastErr: unknown = null;
            for (let i = 0; i < 2 && alive; i++) {
              try {
                await load({ force: true });
                if (alive) setError("");
                lastErr = null;
                break;
              } catch (e) {
                lastErr = e;
                await new Promise((r) => setTimeout(r, 400 * (i + 1)));
              }
            }
            if (alive && lastErr && !chatRef.current) {
              setError(formatApiError(lastErr, t("supportChat.errorLoad")));
            }
            if (alive) setLoading(false);
          }
        } else if (!staffMode) {
          const cached = await loadCachedSupportChat();
          if (alive && cached) {
            hadCache = true;
            const box = await pendingOutboxForTicket(cached.ticket.id, false);
            const extra = box
              .filter((item) => !cached.messages.some((m) => m.id === item.id || m.client_msg_id === item.id))
              .map((item) => ({
                id: item.id,
                body: item.body,
                created_at: item.createdAt,
                is_staff: false,
                pending: false,
              }));
            setChat({
              ...cached,
              messages: [...cached.messages, ...extra].sort(
                (a, b) =>
                  parseServerTime(a.created_at) - parseServerTime(b.created_at)
              ),
            });
            setLoading(false);
            setError("");
            void load()
              .then(() => {
                if (alive) setError("");
              })
              .catch(() => {
                /* keep cached chat */
              });
          }
        }

        // VPN hint — non-blocking
        void ninaVpnGetStatus()
          .then((st) => {
            if (alive) setVpnHint(st === "connected" || st === "connecting");
          })
          .catch(() => {
            if (alive) setVpnHint(false);
          });

        if (!staffMode && !hadCache) {
          if (alive && !chatRef.current) setLoading(true);
          // No cache yet — one fast attempt, then retries without blanking UI
          let lastErr: unknown = null;
          for (let i = 0; i < 3 && alive; i++) {
            try {
              await load();
              if (alive) setError("");
              lastErr = null;
              break;
            } catch (e) {
              lastErr = e;
              await new Promise((r) => setTimeout(r, 600 * (i + 1)));
            }
          }
          if (alive && lastErr && !chatRef.current) {
            setError(formatApiError(lastErr, t("supportChat.errorLoad")));
          }
          if (alive) setLoading(false);
        }

        // Outbox / reconcile in background — never block first paint of the chat
        if (alive) {
          void (async () => {
            try {
              const box = (await loadOutbox()).filter((item) =>
                staffMode ? !!item.staff : !item.staff
              );
              const now = Date.now();
              for (const item of box) {
                if (!alive || item.nextAttemptAt > now) continue;
                if (isSupportSendInFlight()) break;
                // Photos: never background-retry — ACK/POST storms block live sends on MIUI
                if (item.imageUri) {
                  await removeOutbox(item.id);
                  continue;
                }
                const found = await waitForSupportMessage({
                  ticketId: item.ticketId,
                  body: item.body,
                  clientMsgId: item.id,
                  hasImage: false,
                  staff: !!item.staff,
                  attempts: 1,
                  delayMs: 0,
                });
                if (found) {
                  await removeOutbox(item.id);
                  continue;
                }
                try {
                  await sendSupportMessage({
                    ticketId: item.ticketId,
                    body: item.body,
                    clientMsgId: item.id,
                    staff: !!item.staff,
                    timeoutMs: 18000,
                  });
                  await removeOutbox(item.id);
                } catch {
                  await markOutboxAttempt(item.id, true);
                }
              }
              if (box.length && alive) await load({ force: true }).catch(() => {});
            } catch {
              /* ignore background failures */
            }
          })();
        }
      })();

      const timer = setInterval(() => {
        if (chatInFlight || sendingRef.current || isSupportSendInFlight()) return;
        load().catch(() => {});
      }, staffMode ? 12000 : 25000);

      const outboxTimer = setInterval(() => {
        if (!alive || sendingRef.current || isSupportSendInFlight()) return;
        void (async () => {
          const box = (await loadOutbox()).filter((item) =>
            staffMode ? !!item.staff : !item.staff
          );
          if (!box.length) return;
          const now = Date.now();
          let changed = false;
          for (const item of box) {
            if (item.nextAttemptAt > now) continue;
            if (item.imageUri) {
              await removeOutbox(item.id);
              changed = true;
              continue;
            }
            try {
              const found = await waitForSupportMessage({
                ticketId: item.ticketId,
                body: item.body,
                clientMsgId: item.id,
                hasImage: false,
                staff: !!item.staff,
                attempts: 1,
                delayMs: 0,
              });
              if (found) {
                await removeOutbox(item.id);
                changed = true;
                continue;
              }
              await sendSupportMessage({
                ticketId: item.ticketId,
                body: item.body,
                clientMsgId: item.id,
                staff: !!item.staff,
                timeoutMs: 25000,
              });
              await removeOutbox(item.id);
              changed = true;
            } catch {
              await markOutboxAttempt(item.id, true);
            }
          }
          if (changed) await load({ force: true }).catch(() => {});
        })();
      }, 30000);

      // Unstick UI: never let "…" hang forever (was skipped for staffMode)
      const stuckTimer = setInterval(() => {
        if (!alive) return;
        if (sendingRef.current) {
          sendingRef.current = false;
          setSending(false);
        }
        const cur = chatRef.current;
        if (!cur?.ticket?.id) return;
        const now = Date.now();
        const stuckAfter = staffMode ? 12_000 : 4000;
        const stuckLocals = cur.messages.filter(
          (m) =>
            m.pending &&
            (m.id.startsWith("local-") || m.id.startsWith("sent-")) &&
            now - parseServerTime(m.created_at) > stuckAfter
        );
        if (!stuckLocals.length) return;
        void (async () => {
          try {
            if (isSupportSendInFlight()) forceUnlockSupportSend();
            const fresh = await load({ force: true });
            const stillMissing: Message[] = [];
            for (const local of stuckLocals) {
              const needle = (local.body || "").trim();
              const onServer = fresh.messages.find(
                (m) =>
                  m.client_msg_id === local.id ||
                  m.client_msg_id === `${local.id}-0` ||
                  (m.is_staff === !!local.is_staff &&
                    (m.body || "").trim() === needle &&
                    Math.abs(
                      parseServerTime(m.created_at) -
                        parseServerTime(local.created_at)
                    ) < 180_000)
              );
              if (onServer) {
                await removeOutbox(local.id);
                setChat((prev) => {
                  if (!prev) return prev;
                  const without = prev.messages.filter((m) => m.id !== local.id);
                  if (without.some((m) => m.id === onServer.id)) {
                    return { ...prev, messages: without };
                  }
                  return {
                    ...prev,
                    messages: [...without, { ...onServer, pending: false }].sort(
                      (a, b) =>
                        parseServerTime(a.created_at) -
                        parseServerTime(b.created_at)
                    ),
                  };
                });
              } else {
                stillMissing.push(local);
              }
            }
            if (stillMissing.length) {
              setChat((prev) => {
                if (!prev) return prev;
                const ids = new Set(stillMissing.map((s) => s.id));
                return {
                  ...prev,
                  messages: prev.messages.map((m) =>
                    ids.has(m.id) ? { ...m, pending: false } : m
                  ),
                };
              });
              for (const local of stillMissing) {
                await markOutboxAttempt(local.id, true);
              }
            } else {
              setError("");
            }
          } catch {
            forceUnlockSupportSend();
            setChat((prev) => {
              if (!prev) return prev;
              const ids = new Set(stuckLocals.map((s) => s.id));
              return {
                ...prev,
                messages: prev.messages.map((m) =>
                  ids.has(m.id) ? { ...m, pending: false } : m
                ),
              };
            });
          }
        })();
      }, 3000);

      return () => {
        alive = false;
        clearInterval(timer);
        clearInterval(outboxTimer);
        clearInterval(stuckTimer);
      };
    }, [load, staff, staffMode, ticketIdParam, t])
  );

  // Newest-first for inverted FlatList (opens at latest messages)
  const listData = useMemo(() => {
    const msgs = chat?.messages ?? [];
    return [...msgs].reverse();
  }, [chat?.messages]);

  if (staff && !ticketIdParam) {
    return <Redirect href="/(app)/admin-inbox" />;
  }

  const pickPhoto = async () => {
    setError("");
    try {
      const ImagePicker = await import("expo-image-picker");
      const { manipulateAsync, SaveFormat } = await import("expo-image-manipulator");
      const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (!perm.granted) {
        setError(t("supportChat.photoDenied"));
        return;
      }
      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ImagePicker.MediaTypeOptions.Images,
        quality: 0.7,
        allowsEditing: false,
      });
      if (result.canceled || !result.assets?.[0]) return;
      const asset = result.assets[0];
      // Pre-shrink for MIUI: send path only re-encodes a small JPEG
      const compressed = await manipulateAsync(
        asset.uri,
        [{ resize: { width: 720 } }],
        { compress: 0.55, format: SaveFormat.JPEG }
      );
      if (!compressed.uri) {
        setError(t("supportChat.errorSend"));
        return;
      }
      setPendingImage({
        uri: compressed.uri,
        mime: "image/jpeg",
      });
    } catch {
      setError(t("supportChat.errorSend"));
    }
  };

  const send = async () => {
    const body = text.trim();
    // Only a short debounce — never block the composer on network ACK
    if ((!body && !pendingImage) || sending) return;

    setSending(true);
    sendingRef.current = true;
    setError("");
    abortChatLoads();
    pauseSupportPrefetch();
    if (staffMode) pauseAdminSupportPrefetch();

    let current = chat;
    if (!current?.ticket?.id) {
      try {
        current = await load({ force: true });
      } catch (e: unknown) {
        resumeSupportPrefetch();
        resumeAdminSupportPrefetch();
        forceUnlockSupportSend();
        sendingRef.current = false;
        setSending(false);
        setError(formatApiError(e, t("supportChat.errorLoad")));
        return;
      }
      if (!current?.ticket?.id) {
        resumeSupportPrefetch();
        resumeAdminSupportPrefetch();
        forceUnlockSupportSend();
        sendingRef.current = false;
        setSending(false);
        setError(t("supportChat.errorLoad"));
        return;
      }
    }

    const imageUri = pendingImage?.uri || null;
    const tempId = `local-${Date.now()}`;
    const ticketId = current!.ticket.id;
    const outboxBody = body || (imageUri ? "📷 Фото" : "");
    const optimistic: Message = {
      id: tempId,
      body: body || (imageUri ? "📷" : ""),
      created_at: new Date().toISOString(),
      is_staff: !!staffMode,
      image_url: imageUri,
      pending: false,
    };
    setText("");
    setPendingImage(null);
    setChat((prev) => {
      const base = prev ?? current!;
      const next = { ...base, messages: [...base.messages, optimistic] };
      if (!staffMode) void saveCachedSupportChat(next);
      else if (ticketIdParam) {
        void saveCachedAdminTicket({
          ...next,
          user_email: emailParam || undefined,
        });
      }
      return next;
    });
    void addOutbox({
      id: tempId,
      ticketId,
      body: outboxBody,
      imageUri,
      staff: staffMode,
      createdAt: optimistic.created_at,
      attempts: 0,
      nextAttemptAt: 0,
    });

    // Unlock composer only — do NOT clear sendingLock / resume prefetch here.
    // That used to starve the POST on MIUI and leave a fake "sent" bubble.
    setTimeout(() => {
      sendingRef.current = false;
      setSending(false);
    }, staffMode ? 900 : 450);

    const persistChat = (next: Chat) => {
      if (!staffMode) void saveCachedSupportChat(next);
      else if (ticketIdParam) {
        void saveCachedAdminTicket({
          ...next,
          user_email: emailParam || undefined,
        });
      }
    };

    const applyServerMsg = (msg: {
      id: string;
      body: string;
      created_at: string;
      is_staff: boolean;
      image_url?: string | null;
      client_msg_id?: string | null;
    }) => {
      setChat((prev) => {
        if (!prev) return prev;
        const withoutLocal = prev.messages.filter(
          (m) => m.id !== tempId && !sameSupportMsg(m, { ...msg, id: msg.id })
        );
        const next = {
          ...prev,
          messages: [
            ...withoutLocal,
            {
              id: String(msg.id).startsWith("local-") ? tempId : msg.id,
              body: msg.body || outboxBody,
              created_at: msg.created_at,
              is_staff: msg.is_staff,
              image_url: msg.image_url || imageUri,
              client_msg_id: msg.client_msg_id || tempId,
              pending: false,
            },
          ].sort(
            (a, b) =>
              parseServerTime(a.created_at) - parseServerTime(b.created_at)
          ),
        };
        persistChat(next);
        return next;
      });
      void removeOutbox(tempId);
    };

    const findOnServer = (fresh: Chat) => {
      const needle = (outboxBody || "").trim();
      return (
        fresh.messages.find(
          (m) =>
            m.client_msg_id === tempId ||
            m.client_msg_id === `${tempId}-0` ||
            (m.is_staff === !!staffMode &&
              (m.body || "").trim() === needle &&
              Math.abs(
                parseServerTime(m.created_at) -
                  parseServerTime(optimistic.created_at)
              ) < 180_000)
        ) || null
      );
    };

    // Background delivery — must NEVER hold the send button
    void (async () => {
      pauseSupportPrefetch();
      if (staffMode) pauseAdminSupportPrefetch();
      abortChatLoads();
      try {
        const msg = await sendSupportMessage({
          ticketId,
          body,
          imageUri,
          staff: staffMode,
          clientMsgId: tempId,
          timeoutMs: imageUri ? 25000 : 12000,
        });
        if (msg) {
          applyServerMsg(msg);
          setError("");
          resumeSupportPrefetch();
          resumeAdminSupportPrefetch();
          void load({ force: true }).catch(() => {});
          return;
        }
      } catch {
        /* reconcile below */
      }

      // Staff: fail fast (long poll storms were starving the actual POST).
      const polls = staffMode ? 2 : 4;
      for (let i = 0; i < polls; i++) {
        await new Promise((r) => setTimeout(r, staffMode ? 500 : 600));
        try {
          const hit = await waitForSupportMessage({
            ticketId,
            body: outboxBody,
            clientMsgId: tempId,
            hasImage: !!imageUri,
            staff: staffMode,
            attempts: 1,
            delayMs: 0,
          });
          if (hit?.id) {
            applyServerMsg(hit);
            setError("");
            resumeSupportPrefetch();
            resumeAdminSupportPrefetch();
            return;
          }
          if (!staffMode || i === polls - 1) {
            const fresh = await load({ force: true });
            const onServer = findOnServer(fresh);
            if (onServer) {
              applyServerMsg(onServer);
              setError("");
              resumeSupportPrefetch();
              resumeAdminSupportPrefetch();
              return;
            }
          }
        } catch {
          /* keep polling */
        }
      }

      // Keep the bubble and show the time — Telegram often already has it
      setChat((prev) => {
        if (!prev) return prev;
        const next = {
          ...prev,
          messages: prev.messages.map((m) =>
            m.id === tempId ? { ...m, pending: false } : m
          ),
        };
        persistChat(next);
        return next;
      });
      forceUnlockSupportSend();
      resumeSupportPrefetch();
      resumeAdminSupportPrefetch();
      void load({ force: true }).catch(() => {});
    })();
  };

  const title = staffMode
    ? emailParam || t("supportChat.titleClient")
    : t("supportChat.title");

  const empty = !loading && (chat?.messages.length ?? 0) === 0;
  const canSend = (!!text.trim() || !!pendingImage) && !sending;

  return (
    <ScreenBackground>
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === "ios" ? "padding" : "height"}
        keyboardVerticalOffset={Platform.OS === "ios" ? 8 : 0}
      >
        <View style={styles.header}>
          <BackCircleButton
            onPress={() =>
              goBackOr(staffMode ? "/(app)/admin-inbox" : "/(app)/(tabs)/settings")
            }
          />
          <Text style={styles.title} numberOfLines={1}>
            {title}
          </Text>
          <View style={styles.headerSpacer} />
        </View>

        {!staffMode && vpnHint && (
          <Text style={styles.vpnHint}>{t("supportChat.vpnHint")}</Text>
        )}

        {loading && !chat ? (
          <View style={styles.empty}>
            <ActivityIndicator color={colors.accent} />
          </View>
        ) : empty ? (
          <View style={styles.empty}>
            <View style={{ marginBottom: 12 }}>
              <IosEmoji emoji="💬" size={32} />
            </View>
            <Text style={styles.emptyText}>
              {staffMode ? t("supportChat.emptyStaff") : t("supportChat.emptyUser")}
            </Text>
          </View>
        ) : (
          <FlatList
            ref={listRef}
            inverted
            data={listData}
            keyExtractor={(m) => m.id}
            contentContainerStyle={[styles.messages, { flexGrow: 1 }]}
            keyboardShouldPersistTaps="handled"
            maintainVisibleContentPosition={{ minIndexForVisible: 0 }}
            renderItem={({ item }) => {
              const mine = staffMode ? item.is_staff : !item.is_staff;
              const localPreview =
                item.image_url &&
                (item.image_url.startsWith("file:") || item.image_url.startsWith("content:"));
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
                  {!!item.image_url &&
                    (localPreview ? (
                      <Image
                        source={{ uri: item.image_url }}
                        style={styles.msgImage}
                        resizeMode="cover"
                      />
                    ) : (
                      <AuthImage path={item.image_url} />
                    ))}
                  {!!item.body && item.body !== "📷" && (
                    <Text style={styles.bubbleText}>{item.body}</Text>
                  )}
                  <Text style={styles.time}>
                    {item.pending ? "…" : formatMsgTime(item.created_at)}
                  </Text>
                </View>
              );
            }}
          />
        )}

        {!!error && (
          <Pressable
            onPress={() => {
              setError("");
              setLoading(true);
              void load()
                .then(() => setError(""))
                .catch((e) =>
                  setError(formatApiError(e, t("supportChat.errorLoad")))
                )
                .finally(() => setLoading(false));
            }}
          >
            <Text style={styles.error}>{error}</Text>
            <Text style={styles.retryHint}>{t("supportChat.tapRetry")}</Text>
          </Pressable>
        )}

        {!!pendingImage && (
          <View style={styles.previewRow}>
            <Image source={{ uri: pendingImage.uri }} style={styles.previewThumb} />
            <Pressable onPress={() => setPendingImage(null)} hitSlop={8}>
              <Text style={styles.previewClear}>{t("supportChat.removePhoto")}</Text>
            </Pressable>
          </View>
        )}

        <View style={[styles.inputRow, { paddingBottom: inputBottomPad }]}>
          <Pressable
            onPress={() => void pickPhoto()}
            disabled={sending}
            style={styles.photoBtn}
            hitSlop={8}
            accessibilityLabel={t("supportChat.attachPhoto")}
          >
            <Text style={styles.photoBtnText}>＋</Text>
          </Pressable>
          <TextInput
            style={styles.input}
            placeholder={
              staffMode ? t("supportChat.placeholderStaff") : t("supportChat.placeholderUser")
            }
            placeholderTextColor={colors.muted}
            value={text}
            onChangeText={setText}
            multiline
            textAlignVertical="top"
            maxLength={5000}
            editable={!sending || !!chat?.ticket?.id}
          />
          <Pressable
            onPress={() => void send()}
            disabled={!canSend || (loading && !chat)}
            style={[styles.sendBtn, (!canSend || (loading && !chat)) && { opacity: 0.4 }]}
            hitSlop={8}
            accessibilityRole="button"
          >
            {sending ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <Text style={styles.sendText}>↑</Text>
            )}
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
  headerSpacer: { width: 36 },
  title: {
    color: colors.text,
    fontSize: 17,
    fontFamily: fonts.displayBold,
    flex: 1,
    textAlign: "center",
  },
  empty: { flex: 1, justifyContent: "center", paddingHorizontal: 32, alignItems: "center" },
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
  msgImage: {
    width: 200,
    height: 200,
    borderRadius: 12,
    marginBottom: 8,
    backgroundColor: "rgba(0,0,0,0.25)",
  },
  msgImagePlaceholder: {
    width: 200,
    height: 120,
    borderRadius: 12,
    marginBottom: 8,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(0,0,0,0.25)",
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
    marginBottom: 2,
    fontFamily: fonts.body,
  },
  retryHint: {
    color: colors.accent,
    textAlign: "center",
    paddingHorizontal: 16,
    marginBottom: 8,
    fontFamily: fonts.bodySemi,
    fontSize: 13,
  },
  vpnHint: {
    color: colors.muted,
    fontSize: 12,
    fontFamily: fonts.body,
    paddingHorizontal: spacing.md,
    paddingBottom: 8,
    lineHeight: 17,
  },
  previewRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingHorizontal: 16,
    paddingBottom: 8,
  },
  previewThumb: { width: 56, height: 56, borderRadius: 10 },
  previewClear: { color: colors.accent, fontFamily: fonts.bodySemi },
  inputRow: {
    flexDirection: "row",
    alignItems: "flex-end",
    padding: 12,
    gap: 8,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.hairline,
    backgroundColor: "rgba(6,6,8,0.92)",
  },
  photoBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.glassFill,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.glassBorder,
    alignItems: "center",
    justifyContent: "center",
  },
  photoBtnText: { color: colors.text, fontSize: 22, marginTop: -2 },
  input: {
    flex: 1,
    backgroundColor: colors.glassFill,
    // Soft oval, not full pill — pill radius clips multiline text on Android
    borderRadius: 22,
    paddingLeft: 20,
    paddingRight: 18,
    paddingTop: Platform.OS === "android" ? 12 : 10,
    paddingBottom: Platform.OS === "android" ? 12 : 10,
    color: colors.text,
    minHeight: 44,
    maxHeight: 140,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.glassBorder,
    fontFamily: fonts.body,
    lineHeight: 20,
    includeFontPadding: false,
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
