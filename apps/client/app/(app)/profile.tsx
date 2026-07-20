import { router } from "expo-router";
import { useCallback, useState } from "react";
import { useFocusEffect } from "expo-router";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { ScreenTitle } from "../../src/components/NinaLogo";
import { GlassCard } from "../../src/components/GlassCard";
import { PrimaryButton } from "../../src/components/PrimaryButton";
import { ScreenBackground } from "../../src/components/ScreenBackground";
import { api } from "../../src/lib/api";
import { useAuth } from "../../src/lib/auth";
import { colors, fonts, spacing } from "../../src/lib/theme";

type Sub = {
  status: string;
  plan_name?: string;
  expires_at?: string;
};

function daysLeft(expires?: string) {
  if (!expires) return null;
  const diff = new Date(expires).getTime() - Date.now();
  return Math.max(0, Math.ceil(diff / (1000 * 60 * 60 * 24)));
}

export default function ProfileScreen() {
  const { user } = useAuth();
  const [sub, setSub] = useState<Sub | null>(null);

  useFocusEffect(
    useCallback(() => {
      api<Sub | null>("/api/v1/subscriptions/me")
        .then(setSub)
        .catch(() => setSub(null));
    }, [])
  );

  const username = user?.email?.split("@")[0] || "User";
  const remaining = daysLeft(sub?.expires_at ?? undefined);
  const active = sub?.status === "active";

  return (
    <ScreenBackground>
      <ScrollView
        contentContainerStyle={styles.scroll}
        showsVerticalScrollIndicator={false}
      >
        <ScreenTitle>Профиль</ScreenTitle>

        <GlassCard style={styles.userCard}>
          <View style={styles.avatar}>
            <Text style={styles.avatarText}>{username[0]?.toUpperCase()}</Text>
          </View>
          <Text style={styles.name}>{username}</Text>
          <Text style={styles.email}>{user?.email}</Text>
        </GlassCard>

        <Text style={styles.section}>Подписка</Text>
        <GlassCard>
          <View style={styles.subRow}>
            <Text style={styles.plan}>{sub?.plan_name || "Premium Plan"}</Text>
            <Text style={styles.chevron}>›</Text>
          </View>
          {sub?.expires_at ? (
            <Text style={styles.renew}>
              Продление{" "}
              {new Date(sub.expires_at).toLocaleDateString("ru-RU", {
                day: "numeric",
                month: "short",
                year: "numeric",
              })}
            </Text>
          ) : (
            <Text style={styles.renew}>Нет активной подписки</Text>
          )}
          <View style={styles.statsRow}>
            <View>
              <Text style={styles.statLabel}>Осталось</Text>
              <Text style={styles.statVal}>
                {remaining != null ? `${remaining} дн.` : "—"}
              </Text>
            </View>
            <View style={styles.statRight}>
              <Text style={styles.statLabel}>Статус</Text>
              <Text style={[styles.status, active && styles.statusActive]}>
                {active ? "Active" : sub?.status || "Inactive"}
              </Text>
            </View>
          </View>
        </GlassCard>

        <PrimaryButton
          label="Чат поддержки"
          variant="secondary"
          onPress={() => router.push("/(app)/support-chat")}
          style={{ marginTop: spacing.md }}
        />
      </ScrollView>
    </ScreenBackground>
  );
}

const styles = StyleSheet.create({
  scroll: {
    paddingHorizontal: spacing.screen,
    paddingTop: 60,
    paddingBottom: 100,
  },
  userCard: { alignItems: "center", paddingVertical: 28, marginBottom: spacing.md },
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
  statusActive: { color: colors.success },
});
