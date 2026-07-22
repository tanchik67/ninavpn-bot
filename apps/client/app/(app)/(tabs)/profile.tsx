import { router } from "expo-router";
import { useCallback, useState } from "react";
import { useFocusEffect } from "expo-router";
import {
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  View,
  Platform,
  Text as RNText,
} from "react-native";
import { AppText as Text } from "../../../src/components/AppText";
import { ScreenTitle } from "../../../src/components/NinaLogo";
import { GlassCard } from "../../../src/components/GlassCard";
import { PrimaryButton } from "../../../src/components/PrimaryButton";
import { ScreenBackground } from "../../../src/components/ScreenBackground";
import { api } from "../../../src/lib/api";
import { useAuth } from "../../../src/lib/auth";
import { useI18n } from "../../../src/lib/i18n";
import { PROFILE_EMOJIS } from "../../../src/lib/profileEmojis";
import { isEmojiEndpointMissing } from "../../../src/lib/profileEmojiStorage";
import { colors, fonts, radii, spacing } from "../../../src/lib/theme";

type Sub = {
  status: string;
  plan_name?: string;
  expires_at?: string;
};

type UserOut = {
  id: string;
  email: string;
  role: string;
  profile_emoji?: string | null;
};

function daysLeft(expires?: string) {
  if (!expires) return null;
  const diff = new Date(expires).getTime() - Date.now();
  return Math.max(0, Math.ceil(diff / (1000 * 60 * 60 * 24)));
}

const emojiFont = Platform.select({
  ios: "System",
  android: "sans-serif",
  default: undefined,
});

export default function ProfileScreen() {
  const { user, refreshMe, patchUser } = useAuth();
  const { t, locale } = useI18n();
  const [sub, setSub] = useState<Sub | null>(null);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [savingEmoji, setSavingEmoji] = useState(false);
  const [emojiError, setEmojiError] = useState("");

  useFocusEffect(
    useCallback(() => {
      api<Sub | null>("/api/v1/subscriptions/me")
        .then(setSub)
        .catch(() => setSub(null));
    }, [])
  );

  const username = user?.email?.split("@")[0] || t("profile.fallbackUser");
  const remaining = daysLeft(sub?.expires_at ?? undefined);
  const active = sub?.status === "active";
  const dateLocale = locale === "en" ? "en-US" : "ru-RU";
  const emoji = user?.profile_emoji || null;

  const pickEmoji = async (next: string) => {
    const prev = user?.profile_emoji ?? null;
    const value = next || null;
    setEmojiError("");
    setSavingEmoji(true);
    // Instant UI + local cache (works even if API route is not deployed yet)
    patchUser({ profile_emoji: value });
    setPickerOpen(false);
    try {
      const updated = await api<UserOut>("/api/v1/auth/me/emoji", {
        method: "POST",
        body: JSON.stringify({ emoji: next }),
      });
      patchUser({
        profile_emoji: updated.profile_emoji ?? value,
      });
      try {
        await refreshMe();
      } catch {
        /* already patched locally */
      }
    } catch (e: any) {
      if (isEmojiEndpointMissing(e)) {
        // Keep local emoji until server ships /me/emoji
        return;
      }
      patchUser({ profile_emoji: prev });
      setPickerOpen(true);
      setEmojiError(e?.message || t("common.error"));
    } finally {
      setSavingEmoji(false);
    }
  };

  return (
    <ScreenBackground>
      <ScrollView
        contentContainerStyle={styles.scroll}
        showsVerticalScrollIndicator={false}
      >
        <ScreenTitle>{t("profile.title")}</ScreenTitle>

        <GlassCard style={styles.userCard}>
          <Pressable
            style={styles.editBtn}
            onPress={() => router.push("/(app)/account")}
            hitSlop={12}
            accessibilityLabel={t("profile.a11yAccount")}
          >
            <Text style={styles.editIcon}>✏️</Text>
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
              <RNText style={[styles.emojiChipText, { fontFamily: emojiFont }]}>
                {emoji || "＋"}
              </RNText>
            </Pressable>
          </View>
          <Text style={styles.email}>{user?.email}</Text>
        </GlassCard>

        <Text style={styles.section}>{t("profile.subscription")}</Text>
        <GlassCard>
          <View style={styles.subRow}>
            <Text style={styles.plan}>
              {sub?.plan_name || t("profile.defaultPlan")}
            </Text>
            <Text style={styles.chevron}>›</Text>
          </View>
          {sub?.expires_at ? (
            <Text style={styles.renew}>
              {t("profile.renewal", {
                date: new Date(sub.expires_at).toLocaleDateString(dateLocale, {
                  day: "numeric",
                  month: "short",
                  year: "numeric",
                }),
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
        <PrimaryButton
          label={t("password.change")}
          variant="secondary"
          onPress={() => router.push("/(app)/change-password")}
          style={{ marginTop: spacing.sm }}
        />
      </ScrollView>

      <Modal
        visible={pickerOpen}
        transparent
        animationType="fade"
        onRequestClose={() => setPickerOpen(false)}
      >
        <Pressable style={styles.modalBackdrop} onPress={() => setPickerOpen(false)}>
          <Pressable style={styles.modalCard} onPress={(e) => e.stopPropagation()}>
            <Text style={styles.modalTitle}>{t("profile.pickEmoji")}</Text>
            {!!emojiError && <Text style={styles.emojiError}>{emojiError}</Text>}
            <View style={styles.emojiGrid}>
              {PROFILE_EMOJIS.map((e) => (
                <Pressable
                  key={e}
                  style={[
                    styles.emojiCell,
                    emoji === e && styles.emojiCellActive,
                  ]}
                  disabled={savingEmoji}
                  onPress={() => pickEmoji(e)}
                >
                  <RNText style={[styles.emojiCellText, { fontFamily: emojiFont }]}>
                    {e}
                  </RNText>
                </Pressable>
              ))}
            </View>
            {!!emoji && (
              <PrimaryButton
                label={t("profile.clearEmoji")}
                variant="secondary"
                busy={savingEmoji}
                onPress={() => pickEmoji("")}
                style={{ marginTop: spacing.md }}
              />
            )}
            <PrimaryButton
              label={t("common.backPlain")}
              variant="secondary"
              onPress={() => setPickerOpen(false)}
              style={{ marginTop: spacing.sm }}
            />
          </Pressable>
        </Pressable>
      </Modal>
    </ScreenBackground>
  );
}

const styles = StyleSheet.create({
  scroll: {
    paddingHorizontal: spacing.screen,
    paddingTop: 60,
    paddingBottom: 100,
  },
  userCard: {
    alignItems: "center",
    paddingVertical: 28,
    marginBottom: spacing.md,
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
  editIcon: {
    fontSize: 20,
    fontFamily: Platform.select({
      ios: "System",
      android: "sans-serif",
      default: undefined,
    }),
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
  modalBackdrop: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.55)",
    justifyContent: "flex-end",
  },
  modalCard: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: radii.xl,
    borderTopRightRadius: radii.xl,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.glassBorder,
    padding: spacing.lg,
    paddingBottom: 36,
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
  emojiGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "center",
    gap: 8,
  },
  emojiCell: {
    width: 48,
    height: 48,
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
  emojiCellText: {
    fontSize: 24,
  },
});
