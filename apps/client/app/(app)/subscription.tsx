import { useCallback, useState } from "react";
import { useFocusEffect, router } from "expo-router";
import { goBackOr } from "../../src/lib/nav";
import { ActivityIndicator, Pressable, StyleSheet, View } from "react-native";
import { AppText as Text } from "../../src/components/AppText";
import { NinaLogo, ScreenTitle } from "../../src/components/NinaLogo";
import { GlassCard } from "../../src/components/GlassCard";
import { PrimaryButton } from "../../src/components/PrimaryButton";
import { ScreenBackground } from "../../src/components/ScreenBackground";
import { api } from "../../src/lib/api";
import { useI18n } from "../../src/lib/i18n";
import { colors, fonts, spacing } from "../../src/lib/theme";

type Sub = {
  id: string;
  status: string;
  devices: number;
  months: number;
  plan_name?: string;
  expires_at?: string;
  has_config: boolean;
};

export default function SubscriptionScreen() {
  const { t } = useI18n();
  const [sub, setSub] = useState<Sub | null | undefined>(undefined);
  const [error, setError] = useState("");

  useFocusEffect(
    useCallback(() => {
      let alive = true;
      (async () => {
        try {
          const data = await api<Sub | null>("/api/v1/subscriptions/me");
          if (alive) setSub(data);
        } catch (e: any) {
          if (alive) setError(e?.message || t("common.error"));
        }
      })();
      return () => {
        alive = false;
      };
    }, [t])
  );

  return (
    <ScreenBackground>
      <View style={styles.wrap}>
        <Pressable onPress={() => goBackOr("/(app)/(tabs)/profile")} hitSlop={12}>
          <Text style={styles.back}>{t("common.back")}</Text>
        </Pressable>
        <NinaLogo size={24} />
        <ScreenTitle>{t("subscription.title")}</ScreenTitle>

        {sub === undefined ? (
          <ActivityIndicator color={colors.accent} style={{ marginTop: 40 }} />
        ) : !sub ? (
          <GlassCard>
            <Text style={styles.empty}>{t("subscription.empty")}</Text>
            <PrimaryButton
              label={t("subscription.choosePlan")}
              onPress={() => router.push("/(app)/plans")}
            />
          </GlassCard>
        ) : (
          <>
            <View style={styles.stats}>
              <GlassCard style={styles.stat}>
                <Text style={styles.statLabel}>{t("common.status")}</Text>
                <Text style={styles.statValue}>{sub.status}</Text>
              </GlassCard>
              <GlassCard style={styles.stat}>
                <Text style={styles.statLabel}>{t("subscription.devices")}</Text>
                <Text style={styles.statValue}>{sub.devices}</Text>
              </GlassCard>
              <GlassCard style={styles.stat}>
                <Text style={styles.statLabel}>{t("subscription.months")}</Text>
                <Text style={styles.statValue}>{sub.months}</Text>
              </GlassCard>
            </View>

            <GlassCard style={{ gap: 8 }}>
              <Text style={styles.plan}>
                {sub.plan_name || t("subscription.fallbackPlan")}
              </Text>
              <Text style={styles.muted}>
                {t("subscription.until", {
                  date: sub.expires_at
                    ? new Date(sub.expires_at).toLocaleString()
                    : "—",
                })}
              </Text>
              {!!error && <Text style={styles.error}>{error}</Text>}
              <PrimaryButton
                label={t("subscription.openConfig")}
                onPress={() => router.push("/(app)/config")}
              />
              <PrimaryButton
                variant="secondary"
                label={t("subscription.renew")}
                onPress={async () => {
                  const checkout = await api<{ payment_url: string; payment_id: number }>(
                    "/api/v1/subscriptions/me/renew",
                    { method: "POST", body: "{}" }
                  );
                  router.push({
                    pathname: "/(app)/pay",
                    params: { payment_url: checkout.payment_url },
                  });
                }}
              />
            </GlassCard>
          </>
        )}
      </View>
    </ScreenBackground>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, padding: spacing.screen, paddingTop: 56, gap: 14 },
  back: { color: colors.accent, fontFamily: fonts.bodySemi },
  stats: { flexDirection: "row", gap: 8 },
  stat: { flex: 1, paddingVertical: 14 },
  statLabel: {
    color: colors.muted,
    fontSize: 11,
    fontFamily: fonts.bodySemi,
  },
  statValue: {
    color: colors.text,
    fontSize: 16,
    fontFamily: fonts.displayBold,
    marginTop: 4,
  },
  plan: { color: colors.text, fontSize: 18, fontFamily: fonts.bodyBold },
  muted: { color: colors.muted, fontFamily: fonts.body },
  empty: { color: colors.muted, marginBottom: 12, fontFamily: fonts.body },
  error: { color: colors.danger, fontFamily: fonts.body },
});
