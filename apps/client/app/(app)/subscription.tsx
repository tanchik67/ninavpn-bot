import { useCallback, useState } from "react";
import { useFocusEffect, router } from "expo-router";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";
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

  if (sub === undefined) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.accent} />
      </View>
    );
  }

  if (!sub) {
    return (
      <View style={styles.wrap}>
        <Text style={styles.title}>Нет активной подписки</Text>
        <Pressable style={styles.btn} onPress={() => router.push("/(app)/plans")}>
          <Text style={styles.btnText}>Выбрать тариф</Text>
        </Pressable>
      </View>
    );
  }

  return (
    <View style={styles.wrap}>
      <Text style={styles.title}>{sub.plan_name || "Подписка"}</Text>
      <Text style={styles.row}>Статус: {sub.status}</Text>
      <Text style={styles.row}>Устройств: {sub.devices}</Text>
      <Text style={styles.row}>Срок: {sub.months} мес.</Text>
      <Text style={styles.row}>
        До: {sub.expires_at ? new Date(sub.expires_at).toLocaleString() : "—"}
      </Text>
      {!!error && <Text style={styles.error}>{error}</Text>}
      <Pressable style={styles.btn} onPress={() => router.push("/(app)/config")}>
        <Text style={styles.btnText}>Открыть конфиг</Text>
      </Pressable>
      <Pressable
        style={[styles.btn, styles.secondary]}
        onPress={async () => {
          const checkout = await api<{ payment_url: string }>("/api/v1/subscriptions/me/renew", {
            method: "POST",
            body: "{}",
          });
          router.push({ pathname: "/(app)/pay", params: { payment_url: checkout.payment_url } });
        }}
      >
        <Text style={styles.btnText}>Продлить</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, padding: 20, gap: 10 },
  center: { flex: 1, justifyContent: "center", alignItems: "center" },
  title: { color: colors.text, fontSize: 28, fontWeight: "800", marginBottom: 8 },
  row: { color: colors.muted, fontSize: 16 },
  btn: {
    backgroundColor: colors.accent,
    borderRadius: 12,
    padding: 14,
    alignItems: "center",
    marginTop: 12,
  },
  secondary: { backgroundColor: colors.accentDim },
  btnText: { color: colors.bg, fontWeight: "700" },
  error: { color: colors.danger },
});
