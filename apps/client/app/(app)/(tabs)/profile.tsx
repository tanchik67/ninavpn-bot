import { router } from "expo-router";
import { useCallback, useState } from "react";
import { useFocusEffect } from "expo-router";
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text as RNText,
  useWindowDimensions,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { AppText as Text } from "../../../src/components/AppText";
import { IosEmoji } from "../../../src/components/IosEmoji";
import { ScreenTitle } from "../../../src/components/NinaLogo";
import { GlassCard } from "../../../src/components/GlassCard";
import { PrimaryButton } from "../../../src/components/PrimaryButton";
import { ScreenBackground } from "../../../src/components/ScreenBackground";
import { api } from "../../../src/lib/api";
import { formatApiError } from "../../../src/lib/apiErrors";
import { useAuth } from "../../../src/lib/auth";
import { formatProfileDate, useI18n } from "../../../src/lib/i18n";
import { PROFILE_EMOJIS } from "../../../src/lib/profileEmojis";
import { isEmojiEndpointMissing } from "../../../src/lib/profileEmojiStorage";
import {
  isSubscriptionActive,
  loadCachedSubscription,
  saveCachedSubscription,
  type CachedSubscription,
} from "../../../src/lib/subscriptionCache";
import { getDockClearance, useFontScale } from "../../../src/lib/textSize";
import { colors, fonts, radii, spacing } from "../../../src/lib/theme";

type Sub = CachedSubscription;

function localizedPlanName(sub: Sub | null, t: (path: string) => string): string {
  const key = String(sub?.plan_key || "").toLowerCase();
  const name = String(sub?.plan_name || "").trim();
  const compact = name.toLowerCase().replace(/\s+/g, " ");
  const welcome =
    key === "welcome_3m" ||
    key.includes("welcome") ||
    /^welcome$/i.test(name) ||
    /3\s*месяц/i.test(compact) ||
    (sub?.months === 3 && String(sub?.status || "").toLowerCase() === "trial");
  if (welcome) return t("profile.welcomePlan");
  return name || t("profile.defaultPlan");
}

type UserOut = {
  id: string;
  email: string;
  role: string;
  profile_emoji?: string | null;
};

const COLS = 6;
const CELL_GAP = 8;

function daysLeft(expires?: string) {
  if (!expires) return null;
  const diff = new Date(expires).getTime() - Date.now();
  return Math.max(0, Math.ceil(diff / (1000 * 60 * 60 * 24)));
}

export default function ProfileScreen() {
  const { width: winW, height: winH } = useWindowDimensions();
  const insets = useSafeAreaInsets();
  const scale = useFontScale();
  const { user, patchUser } = useAuth();
  const { t, locale } = useI18n();
  const [sub, setSub] = useState<Sub | null>(null);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [emojiError, setEmojiError] = useState("");

  const sheetPad = spacing.lg;
  const contentW = Math.min(winW, 480) - sheetPad * 2;
  const cellSize = Math.floor((contentW - CELL_GAP * (COLS - 1)) / COLS);
  // Lift sheet above floating tab dock (absolute overlay cannot cover native tab bar)
  const sheetBottomPad = getDockClearance(scale, insets.bottom);

  useFocusEffect(
    useCallback(() => {
      let alive = true;
      (async () => {
        const cached = await loadCachedSubscription();
        if (alive && cached) setSub(cached);
        try {
          const next = await api<Sub | null>("/api/v1/subscriptions/me", {
            timeoutMs: 12000,
            retries: 1,
          });
          if (!alive) return;
          setSub(next);
          void saveCachedSubscription(next);
        } catch (e: any) {
          const msg = String(e?.message || "");
          if (msg === "not_authenticated" || /invalid_refresh|unauthorized/i.test(msg)) {
            if (alive) setSub(null);
            void saveCachedSubscription(null);
          }
          // Keep cache on timeouts — don't flash Inactive
        }
      })();
      return () => {
        alive = false;
      };
    }, [])
  );

  const username = user?.email?.split("@")[0] || t("profile.fallbackUser");
  const remaining = daysLeft(sub?.expires_at ?? undefined);
  const active = isSubscriptionActive(sub);
  const emoji = user?.profile_emoji || null;

  const closePicker = () => {
    setPickerOpen(false);
    setEmojiError("");
  };

  /** Optimistic: update UI immediately, sync API in background (never lock the picker). */
  const pickEmoji = (next: string) => {
    const prev = user?.profile_emoji ?? null;
    const value = next || null;
    setEmojiError("");
    patchUser({ profile_emoji: value });
    setPickerOpen(false);

    void (async () => {
      try {
        const updated = await api<UserOut>("/api/v1/auth/me/emoji", {
          method: "POST",
          body: JSON.stringify({ emoji: next }),
        });
        patchUser({
          profile_emoji: updated.profile_emoji ?? value,
        });
      } catch (e: unknown) {
        if (isEmojiEndpointMissing(e)) {
          return;
        }
        patchUser({ profile_emoji: prev });
        setEmojiError(formatApiError(e, t("common.error")));
        setPickerOpen(true);
      }
    })();
  };

  return (
    <ScreenBackground>
      <View style={styles.screenRoot}>
      <ScrollView
        contentContainerStyle={styles.scroll}
        showsVerticalScrollIndicator={false}
      >
        <ScreenTitle>{t("profile.title")}</ScreenTitle>

        <View style={styles.userCardWrap}>
          <GlassCard style={styles.userCard}>
            <Pressable
              style={styles.editBtn}
              onPress={() => router.push("/(app)/account")}
              hitSlop={12}
              accessibilityLabel={t("profile.a11yAccount")}
            >
              <IosEmoji emoji="✏️" size={18} />
            </Pressable>
            <View style={styles.avatar}>
              <Text style={styles.avatarText}>{username[0]?.toUpperCase()}</Text>
            </View>
            <View style={styles.nameRow}>
              <Text style={styles.name}>{username}</Text>
              <Pressable
                onPress={() => setPickerOpen(true)}
                hitSlop={8}
                accessibilityLabel={t("profile.pickEmoji")}
                style={styles.emojiChip}
              >
                {emoji ? (
                  <IosEmoji emoji={emoji} size={20} />
                ) : (
                  <RNText style={styles.emojiChipText} allowFontScaling={false}>
                    ＋
                  </RNText>
                )}
              </Pressable>
            </View>
            <Text style={styles.email}>{user?.email}</Text>
          </GlassCard>
        </View>

        <Text style={styles.section}>{t("profile.subscription")}</Text>
        <GlassCard>
          <View style={styles.subRow}>
            <Text style={styles.plan}>
              {localizedPlanName(sub, t)}
            </Text>
            <Text style={styles.chevron}>›</Text>
          </View>
          {sub?.expires_at ? (
            <Text style={styles.renew}>
              {t("profile.renewal", {
                date: formatProfileDate(sub.expires_at, locale, t),
              })}
            </Text>
          ) : (
            <Text style={styles.renew}>{t("profile.noActiveSub")}</Text>
          )}
          <View style={styles.statsRow}>
            <View>
              <Text style={styles.statLabel}>{t("profile.remaining")}</Text>
              <Text style={styles.statVal}>
                {remaining != null
                  ? t("profile.daysLeft", { n: remaining })
                  : "—"}
              </Text>
            </View>
            <View style={styles.statRight}>
              <Text style={styles.statLabel}>{t("common.status")}</Text>
              <Text style={[styles.status, active && styles.statusActive]}>
                {active
                  ? t("profile.statusActive")
                  : t("profile.statusInactive")}
              </Text>
            </View>
          </View>
        </GlassCard>

        <PrimaryButton
          label={t("referral.title")}
          variant="secondary"
          onPress={() => router.push("/(app)/referral")}
          style={{ marginTop: spacing.md }}
        />
        <PrimaryButton
          label={
            user?.role === "admin" || user?.role === "support"
              ? t("support.staffChats")
              : t("support.userChat")
          }
          variant="secondary"
          onPress={() =>
            router.push(
              user?.role === "admin" || user?.role === "support"
                ? "/(app)/admin-inbox"
                : "/(app)/support-chat"
            )
          }
          style={{ marginTop: spacing.md }}
        />
      </ScrollView>

      {/*
        No RN Modal — on Android + New Arch it often mounts at 0×0 (top-left).
        Full-screen absolute overlay with explicit pixel size instead.
      */}
      {pickerOpen ? (
        <View style={styles.overlayRoot}>
          {/* Top half: tap to dismiss — must NOT cover the sheet */}
          <Pressable
            style={styles.overlayDismiss}
            onPress={closePicker}
            accessibilityRole="button"
          />
          <View style={[styles.sheet, { paddingBottom: sheetBottomPad }]}>
            <View style={styles.sheetHandle} />
            <Text style={styles.modalTitle}>{t("profile.pickEmoji")}</Text>
            {!!emojiError && <Text style={styles.emojiError}>{emojiError}</Text>}
            <ScrollView
              style={[styles.emojiScroll, { maxHeight: Math.min(320, Math.round(winH * 0.4)) }]}
              contentContainerStyle={styles.emojiGrid}
              keyboardShouldPersistTaps="handled"
              nestedScrollEnabled
            >
              {PROFILE_EMOJIS.map((e) => (
                <Pressable
                  key={e}
                  style={[
                    styles.emojiCell,
                    { width: cellSize, height: cellSize },
                    emoji === e && styles.emojiCellActive,
                  ]}
                  onPress={() => pickEmoji(e)}
                >
                  <IosEmoji emoji={e} size={Math.round(cellSize * 0.55)} />
                </Pressable>
              ))}
            </ScrollView>
            {!!emoji && (
              <PrimaryButton
                label={t("profile.clearEmoji")}
                variant="secondary"
                onPress={() => pickEmoji("")}
                style={{ marginTop: spacing.md }}
              />
            )}
            <PrimaryButton
              label={t("common.backPlain")}
              variant="secondary"
              onPress={closePicker}
              style={{ marginTop: spacing.sm }}
            />
          </View>
        </View>
      ) : null}
      </View>
    </ScreenBackground>
  );
}

const styles = StyleSheet.create({
  screenRoot: {
    flex: 1,
  },
  scroll: {
    paddingHorizontal: spacing.screen,
    paddingTop: 60,
    paddingBottom: 100,
  },
  userCardWrap: {
    marginBottom: spacing.md,
  },
  userCard: {
    alignItems: "center",
    paddingVertical: 28,
    position: "relative",
  },
  editBtn: {
    position: "absolute",
    top: 12,
    right: 12,
    zIndex: 2,
    width: 36,
    height: 36,
    alignItems: "center",
    justifyContent: "center",
  },
  avatar: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: colors.glassFill,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.glassBorder,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 12,
  },
  avatarText: {
    color: colors.muted,
    fontSize: 28,
    fontFamily: fonts.displayBold,
  },
  nameRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    maxWidth: "100%",
    paddingHorizontal: 12,
  },
  emojiChip: {
    minWidth: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: colors.glassFill,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.glassBorder,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 6,
  },
  emojiChipText: {
    fontSize: 18,
    color: colors.muted,
  },
  name: {
    fontFamily: fonts.displayBold,
    fontSize: 20,
    color: colors.text,
  },
  email: {
    fontFamily: fonts.body,
    color: colors.muted,
    marginTop: 4,
  },
  section: {
    fontFamily: fonts.bodySemi,
    fontSize: 13,
    color: colors.muted,
    textTransform: "uppercase",
    letterSpacing: 0.6,
    marginBottom: 8,
    marginLeft: 4,
  },
  subRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  plan: {
    fontFamily: fonts.bodyBold,
    fontSize: 17,
    color: colors.text,
  },
  chevron: { color: colors.muted, fontSize: 22 },
  renew: {
    fontFamily: fonts.body,
    color: colors.muted,
    fontSize: 13,
    marginTop: 6,
  },
  statsRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginTop: 14,
    paddingTop: 14,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.hairline,
  },
  statLabel: {
    fontFamily: fonts.body,
    color: colors.muted,
    fontSize: 12,
  },
  statVal: {
    fontFamily: fonts.bodyBold,
    color: colors.text,
    marginTop: 4,
  },
  statRight: { alignItems: "flex-end" },
  status: {
    fontFamily: fonts.bodyBold,
    color: colors.muted,
    marginTop: 4,
  },
  statusActive: {
    color: "#22C55E",
  },
  overlayRoot: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    zIndex: 1000,
    elevation: 1000,
    flexDirection: "column",
    justifyContent: "flex-end",
    backgroundColor: "rgba(0,0,0,0.55)",
  },
  overlayDismiss: {
    flexGrow: 1,
    flexShrink: 1,
    width: "100%",
    minHeight: 80,
  },
  sheet: {
    width: "100%",
    flexGrow: 0,
    flexShrink: 0,
    backgroundColor: colors.surface,
    borderTopLeftRadius: radii.xl,
    borderTopRightRadius: radii.xl,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.glassBorder,
    paddingHorizontal: spacing.lg,
    paddingTop: 10,
  },
  sheetHandle: {
    alignSelf: "center",
    width: 40,
    height: 4,
    borderRadius: 2,
    backgroundColor: colors.glassBorder,
    marginBottom: 12,
  },
  modalTitle: {
    fontFamily: fonts.displayBold,
    fontSize: 18,
    color: colors.text,
    textAlign: "center",
    marginBottom: spacing.md,
  },
  emojiError: {
    color: colors.danger,
    fontFamily: fonts.body,
    textAlign: "center",
    marginBottom: spacing.sm,
    fontSize: 13,
  },
  emojiScroll: {
    flexGrow: 0,
  },
  emojiGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: CELL_GAP,
    paddingBottom: 4,
  },
  emojiCell: {
    borderRadius: 14,
    backgroundColor: colors.glassFill,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.glassBorder,
    alignItems: "center",
    justifyContent: "center",
  },
  emojiCellActive: {
    borderColor: colors.accent,
    backgroundColor: "rgba(123,47,255,0.2)",
  },
});
