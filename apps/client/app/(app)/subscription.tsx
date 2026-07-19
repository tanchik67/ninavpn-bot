import { useCallback, useState } from "react";
import { useFocusEffect, router } from "expo-router";
import { ActivityIndicator, StyleSheet, Text, View } from "react-native";
import { BrandMark } from "../../src/components/BrandMark";
import { GlassCard } from "../../src/components/GlassCard";
import { GradientButton } from "../../src/components/GradientButton";
import { ScreenBackground } from "../../src/components/ScreenBackground";
import { api } from "../../src/lib/api";
import { colors } from "../../src/lib/theme";

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
          if (alive) setError(e?.message || "Ошибка");
        }
      })();
      return () => {
        alive = false;
      };
    }, [])
  );

  return (
    <ScreenBackground>
      <View style={styles.wrap}>
        <BrandMark size={26} />
        <Text style={styles.title}>Data & Status</Text>

        {sub === undefined ? (
          <ActivityIndicator color={colors.accentPink} style={{ marginTop: 40 }} />
        ) : !sub ? (
          <GlassCard>
            <Text style={styles.empty}>Нет активной подписки</Text>
            <GradientButton label="Выбрать тариф" onPress={() => router.push("/(app)/plans")} />
          </GlassCard>
        ) : (
          <>
            <View style={styles.stats}>
              <GlassCard style={styles.stat}>
                <Text style={styles.statLabel}>Status</Text>
                <Text style={styles.statValue}>{sub.status}</Text>
              </GlassCard>
              <GlassCard style={styles.stat}>
                <Text style={styles.statLabel}>Devices</Text>
                <Text style={styles.statValue}>{sub.devices}</Text>
              </GlassCard>
              <GlassCard style={styles.stat}>
                <Text style={styles.statLabel}>Months</Text>
                <Text style={styles.statValue}>{sub.months}</Text>
              </GlassCard>
            </View>

            <GlassCard style={{ gap: 8 }}>
              <Text style={styles.plan}>{sub.plan_name || "Подписка"}</Text>
              <Text style={styles.muted}>
                До: {sub.expires_at ? new Date(sub.expires_at).toLocaleString() : "—"}
              </Text>
              {!!error && <Text style={styles.error}>{error}</Text>}
              <GradientButton label="Открыть конфиг" onPress={() => router.push("/(app)/home")} />
              <GradientButton
                variant="ghost"
                label="Продлить"
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
  wrap: { flex: 1, padding: 20, paddingTop: 56, gap: 14 },
  title: { color: colors.text, fontSize: 28, fontWeight: "900" },
  stats: { flexDirection: "row", gap: 8 },
  stat: { flex: 1, paddingVertical: 14 },
  statLabel: { color: colors.muted, fontSize: 11, fontWeight: "700" },
  statValue: { color: colors.text, fontSize: 18, fontWeight: "900", marginTop: 4 },
  plan: { color: colors.text, fontSize: 20, fontWeight: "800" },
  muted: { color: colors.muted },
  empty: { color: colors.muted, marginBottom: 12 },
  error: { color: colors.danger },
});
