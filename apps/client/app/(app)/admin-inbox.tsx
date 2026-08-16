import { Redirect, router } from "expo-router";
import { goBackOr } from "../../src/lib/nav";
import { useCallback, useState } from "react";
import { useFocusEffect } from "expo-router";
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  StyleSheet,
  View,
} from "react-native";
import { AppText as Text } from "../../src/components/AppText";
import { BackCircleButton } from "../../src/components/BackCircleButton";
import { ScreenBackground } from "../../src/components/ScreenBackground";
import { api } from "../../src/lib/api";
import {
  loadCachedAdminInbox,
  saveCachedAdminInbox,
  type AdminTicketRow,
} from "../../src/lib/adminSupportCache";
import {
  peekCachedAdminInbox,
} from "../../src/lib/adminSupportCache";
import {
  prefetchAdminInbox,
  prefetchAdminTicket,
  warmAdminTickets,
} from "../../src/lib/adminSupportPrefetch";
import { bumpOutboxNow } from "../../src/lib/supportOutbox";
import { flushSupportOutbox } from "../../src/lib/supportOutboxFlush";
import { useAuth } from "../../src/lib/auth";
import { useI18n } from "../../src/lib/i18n";
import { colors, fonts, radii, spacing } from "../../src/lib/theme";

type TicketRow = AdminTicketRow;

function isStaffRole(role?: string) {
  return role === "admin" || role === "support";
}

export default function AdminInboxScreen() {
  const { user } = useAuth();
  const { t } = useI18n();
  const [rows, setRows] = useState<TicketRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const statusLabel = (status: string) => {
    if (status === "answered") return t("adminInbox.statusAnswered");
    if (status === "open") return t("adminInbox.statusOpen");
    return status;
  };

  const load = useCallback(async (quiet = false) => {
    const data = await api<TicketRow[]>("/api/v1/support/admin/tickets", {
      timeoutMs: 8000,
      retries: 0,
      priority: !quiet,
    });
    setRows(data);
    await saveCachedAdminInbox(data);
    setError("");
    // Quiet polls must not re-warm tickets (that fights the open chat fetch).
    if (!quiet) void warmAdminTickets(data);
  }, []);

  useFocusEffect(
    useCallback(() => {
      if (!isStaffRole(user?.role)) return;
      let alive = true;

      (async () => {
        // Instant paint: memory first, then AsyncStorage
        const mem = peekCachedAdminInbox();
        const cached = mem || (await loadCachedAdminInbox());
        if (!alive) return;
        if (cached?.length) {
          setRows(cached);
          setLoading(false);
          setError("");
          void warmAdminTickets(cached);
        } else {
          setLoading(true);
        }

        try {
          await load(!!cached?.length);
          if (alive) setError("");
        } catch {
          if (alive && !cached?.length) {
            // Try shared prefetch once more
            const again = await prefetchAdminInbox({ force: true, attempts: 2 });
            if (alive && again?.length) {
              setRows(again);
              setError("");
            } else if (alive && !cached?.length) {
              setError(t("adminInbox.errorLoad"));
            }
          }
        } finally {
          if (alive) setLoading(false);
        }

        // Deliver any staff replies that never left the phone
        void bumpOutboxNow().then(() =>
          flushSupportOutbox({ staffOnly: true, ignoreSchedule: true })
        );
      })();

      const timer = setInterval(() => {
        load(true).catch(() => {});
      }, 25000);
      return () => {
        alive = false;
        clearInterval(timer);
      };
    }, [load, user?.role, t])
  );

  if (!isStaffRole(user?.role)) {
    return <Redirect href="/(app)/support-chat" />;
  }

  return (
    <ScreenBackground>
      <View style={styles.header}>
        <BackCircleButton onPress={() => goBackOr("/(app)/(tabs)/settings")} />
        <Text style={styles.title}>{t("adminInbox.title")}</Text>
        <View style={styles.headerSpacer} />
      </View>

      {loading && !rows.length ? (
        <View style={styles.center}>
          <ActivityIndicator color={colors.accent} />
        </View>
      ) : error && !rows.length ? (
        <View style={styles.center}>
          <Text style={styles.error}>{error}</Text>
        </View>
      ) : rows.length === 0 ? (
        <View style={styles.center}>
          <Text style={styles.emptyEmoji}>📭</Text>
          <Text style={styles.emptyText}>{t("adminInbox.empty")}</Text>
        </View>
      ) : (
        <FlatList
          data={rows}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.list}
          renderItem={({ item }) => {
            const waiting = item.status === "open" && !item.last_is_staff;
            return (
              <Pressable
                style={[styles.row, waiting && styles.rowWaiting]}
                onPress={() => {
                  // Always refresh thread — stale cache had wrong is_staff labels
                  void prefetchAdminTicket(item.id, {
                    force: true,
                    inboxRow: item,
                  });
                  router.push({
                    pathname: "/(app)/support-chat",
                    params: { ticketId: item.id, email: item.user_email },
                  });
                }}
              >
                <View style={styles.rowTop}>
                  <Text style={styles.email} numberOfLines={1}>
                    {item.user_email}
                  </Text>
                  <Text style={[styles.badge, waiting && styles.badgeHot]}>
                    {statusLabel(item.status)}
                  </Text>
                </View>
                <Text style={styles.preview} numberOfLines={2}>
                  {item.last_message || item.subject}
                </Text>
                {!!item.last_message_at && (
                  <Text style={styles.time}>
                    {new Date(item.last_message_at).toLocaleString([], {
                      day: "2-digit",
                      month: "2-digit",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </Text>
                )}
              </Pressable>
            );
          }}
        />
      )}
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
  },
  center: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: 32,
  },
  emptyEmoji: { fontSize: 32, marginBottom: 12 },
  emptyText: {
    color: colors.muted,
    textAlign: "center",
    fontFamily: fonts.body,
  },
  error: { color: colors.danger, fontFamily: fonts.body, textAlign: "center" },
  list: {
    paddingHorizontal: spacing.screen,
    paddingBottom: 110,
    gap: 10,
  },
  row: {
    backgroundColor: colors.glassFill,
    borderRadius: radii.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.glassBorder,
    padding: 14,
  },
  rowWaiting: {
    borderColor: "rgba(123,47,255,0.45)",
  },
  rowTop: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 8,
    marginBottom: 6,
  },
  email: {
    flex: 1,
    color: colors.text,
    fontFamily: fonts.bodySemi,
    fontSize: 15,
  },
  badge: {
    color: colors.muted,
    fontSize: 11,
    fontFamily: fonts.bodySemi,
  },
  badgeHot: { color: colors.accent },
  preview: {
    color: colors.muted,
    fontFamily: fonts.body,
    fontSize: 14,
    lineHeight: 20,
  },
  time: {
    marginTop: 8,
    color: "rgba(255,255,255,0.4)",
    fontSize: 11,
    fontFamily: fonts.body,
  },
});
