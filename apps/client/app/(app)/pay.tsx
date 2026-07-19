import { router, useLocalSearchParams } from "expo-router";
import { useEffect, useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";
import * as WebBrowser from "expo-web-browser";
import { api } from "../../src/lib/api";
import { colors } from "../../src/lib/theme";

export default function PayScreen() {
  const params = useLocalSearchParams<{ plan_key?: string; payment_url?: string }>();
  const [status, setStatus] = useState("Готовим оплату…");
  const [paymentId, setPaymentId] = useState<number | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    (async () => {
      try {
        if (params.payment_url) {
          await WebBrowser.openBrowserAsync(String(params.payment_url));
          setStatus("Завершите оплату в браузере, затем подтвердите.");
          return;
        }
        if (!params.plan_key) {
          setError("Не выбран тариф");
          return;
        }
        const checkout = await api<{
          payment_id: number;
          payment_url: string;
          provider: string;
        }>("/api/v1/payments/checkout", {
          method: "POST",
          body: JSON.stringify({ plan_key: params.plan_key, provider: "mock" }),
        });
        setPaymentId(checkout.payment_id);
        if (checkout.provider === "mock") {
          setStatus("Dev mock: подтвердите оплату кнопкой ниже");
        } else {
          await WebBrowser.openBrowserAsync(checkout.payment_url);
          setStatus("Оплатите в браузере. Конфиг появится на вкладке «Конфиг».");
        }
      } catch (e: any) {
        setError(e?.message || "Ошибка checkout");
      }
    })();
  }, [params.plan_key, params.payment_url]);

  const confirmMock = async () => {
    if (!paymentId) return;
    try {
      await api(`/api/v1/payments/mock/confirm/${paymentId}`, { method: "POST" });
      setStatus("Оплата подтверждена. Идёт выдача доступа…");
      setTimeout(() => router.replace("/(app)/config"), 1500);
    } catch (e: any) {
      setError(e?.message || "confirm failed");
    }
  };

  return (
    <View style={styles.wrap}>
      <Text style={styles.title}>Оплата</Text>
      {!error && !paymentId && !params.payment_url ? (
        <ActivityIndicator color={colors.accent} />
      ) : null}
      <Text style={styles.status}>{status}</Text>
      {!!error && <Text style={styles.error}>{error}</Text>}
      {paymentId ? (
        <Pressable style={styles.btn} onPress={confirmMock}>
          <Text style={styles.btnText}>Подтвердить mock-оплату</Text>
        </Pressable>
      ) : null}
      <Pressable style={styles.secondary} onPress={() => router.replace("/(app)/subscription")}>
        <Text style={styles.btnText}>К подписке</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, padding: 20, gap: 14 },
  title: { color: colors.text, fontSize: 28, fontWeight: "800" },
  status: { color: colors.muted },
  error: { color: colors.danger },
  btn: {
    backgroundColor: colors.accent,
    borderRadius: 12,
    padding: 14,
    alignItems: "center",
  },
  secondary: {
    backgroundColor: colors.surface,
    borderRadius: 12,
    padding: 14,
    alignItems: "center",
    borderWidth: 1,
    borderColor: colors.border,
  },
  btnText: { color: colors.text, fontWeight: "700" },
});
